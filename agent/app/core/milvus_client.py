"""Milvus client factory module"""

from loguru import logger
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    MilvusClient,
    connections,
    utility,
    MilvusException,
)

from app.config import config


def _patch_pymilvus_milvus_client_orm_alias() -> None:
    """
    langchain_milvus internally created MilvusClient sets _using to ``cm-{id}``,
    that alias is not registered in pymilvus.orm.connections; then ORM ``Collection(..., using=...)``
    raises ConnectionNotExistException: should create connection first.

    After ``connections.connect(alias="default", ...)`` has established a connection,
    force MilvusClient to use the ``default`` alias so it matches ORM.
    """
    if getattr(_patch_pymilvus_milvus_client_orm_alias, "_done", False):
        return
    try:
        from pymilvus.milvus_client.milvus_client import MilvusClient
    except ImportError:
        return

    # Saves the original constructor method.
    _orig_init = MilvusClient.__init__

    def _wrapped_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        _orig_init(self, *args, **kwargs)
        self._using = "default"

    MilvusClient.__init__ = _wrapped_init  # type: ignore[method-assign]
    # Marks the patch as already applied.
    setattr(_patch_pymilvus_milvus_client_orm_alias, "_done", True)


class MilvusClientManager:
    """Milvus client manager"""

    # Constant definitions
    COLLECTION_NAME: str = "biz"
    VECTOR_DIM: int = 1024  # Use 1024 dimensions consistently
    ID_MAX_LENGTH: int = 100
    CONTENT_MAX_LENGTH: int = 8000
    DEFAULT_SHARD_NUMBER: int = 2 # Shards help split data internally

    def __init__(self) -> None:
        """Initialize Milvus client manager"""
        self._client: MilvusClient | None = None
        self._collection: Collection | None = None

    def connect(self) -> MilvusClient:
        """
        Connect to Milvus server and initialize collection

        Returns:
            MilvusClient: Milvus client instance

        Raises:
            RuntimeError: Raised when connection or initialization fails
        """
        # Idempotent: import phase may have connected early via VectorStoreManager; avoid duplicate initialization
        if self._collection is not None and self._client is not None:
            logger.debug("Milvus already connected; skipping duplicate connect")
            return self._client

        try:
            _patch_pymilvus_milvus_client_orm_alias()

            logger.info(f"Connecting to Milvus: {config.milvus_host}:{config.milvus_port}")

            # Establish connection
            connections.connect(
                alias="default",
                host=config.milvus_host,
                port=str(config.milvus_port),
                timeout=config.milvus_timeout / 1000,  # convert to seconds
            )

            # Create client
            uri = f"http://{config.milvus_host}:{config.milvus_port}"
            self._client = MilvusClient(uri=uri)

            logger.info("Connected to Milvus successfully")

            # Check and create collection
            if not self._collection_exists():
                logger.info(f"collection '{self.COLLECTION_NAME}' does not exist; creating...")
                self._create_collection()
                logger.info(f"Created collection successfully '{self.COLLECTION_NAME}'")
            else:
                logger.info(f"collection '{self.COLLECTION_NAME}' already exists")
                self._collection = Collection(self.COLLECTION_NAME)
                
                # Check whether vector dimensions match
                schema = self._collection.schema
                vector_field = None
                existing_dim = None
                for field in schema.fields:
                    if field.name == "vector":
                        vector_field = field
                        break
                
                if vector_field and hasattr(vector_field, 'params') and 'dim' in vector_field.params:
                    existing_dim = vector_field.params['dim']
                    if existing_dim != self.VECTOR_DIM:
                        logger.warning(
                            f"Detected vector dimension mismatch! Current collection dimension: {existing_dim}, configured dimension: {self.VECTOR_DIM}"
                        )
                        logger.info(f"Deleting old collection '{self.COLLECTION_NAME}'...")
                        _ = utility.drop_collection(self.COLLECTION_NAME)
                        logger.info(f"Recreating collection '{self.COLLECTION_NAME}'...")
                        self._create_collection()
                        logger.info(f"Recreated collection successfully, dimension: {self.VECTOR_DIM}")
                    else:
                        logger.info(f"Vector dimension matches: {self.VECTOR_DIM}")

            # Load collection
            self._load_collection()

            return self._client

        except MilvusException as e:
            logger.error(f"Milvus operation failed: {e}")
            self.close()
            raise RuntimeError(f"Milvus operation failed: {e}") from e
        except ConnectionError as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            self.close()
            raise RuntimeError(f"Failed to connect to Milvus: {e}") from e
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            self.close()
            raise RuntimeError(f"Failed to connect to Milvus: {e}") from e

    def _collection_exists(self) -> bool:
        """Check whether collection exists"""
        # pymilvus type annotations may be inaccurate; actual return is bool
        result = utility.has_collection(self.COLLECTION_NAME)
        return bool(result)  # type: ignore[arg-type]

    def _create_collection(self) -> None:
        """Create biz collection"""
        # Define fields
        fields = [
            FieldSchema(
                name="id",
                dtype=DataType.VARCHAR,
                max_length=self.ID_MAX_LENGTH,
                is_primary=True,
            ),
            FieldSchema(
                name="vector",
                dtype=DataType.FLOAT_VECTOR,
                dim=self.VECTOR_DIM,
            ),
            FieldSchema(
                name="content",
                dtype=DataType.VARCHAR,
                max_length=self.CONTENT_MAX_LENGTH,
            ),
            FieldSchema(
                name="metadata",
                dtype=DataType.JSON,
            ),
        ]

        # Create schema
        schema = CollectionSchema(
            fields=fields,
            description="Business knowledge collection",
            enable_dynamic_field=False,
        )

        # Create collection
        self._collection = Collection(
            name=self.COLLECTION_NAME,
            schema=schema,
            num_shards=self.DEFAULT_SHARD_NUMBER,
        )

        # Create index
        self._create_index()

    def _create_index(self) -> None:
        """Create index for vector field"""
        if self._collection is None:
            raise RuntimeError("Collection is not initialized")

        index_params = {
            "metric_type": "L2",  # Euclidean distance
            "index_type": "IVF_FLAT", #Use the IVF_FLAT index type. It clusters vectors into groups, then searches only the most relevant groups instead of scanning everything.
            "params": {"nlist": 128}, # Create 128 clusters/lists
        }

        _ = self._collection.create_index(
            field_name="vector",
            index_params=index_params,
        )

        logger.info("Successfully created index for vector field")

    def _load_collection(self) -> None:
        """Load collection into memory"""
        if self._collection is None:
            self._collection = Collection(self.COLLECTION_NAME)

        # Check whether collection is loaded, compatible with multiple versions
        try:
            # Method 1: try utility.load_state in newer versions
            load_state = utility.load_state(self.COLLECTION_NAME)
            # load_state returns a string or enum such as "Loaded" or "NotLoad"
            state_name = getattr(load_state, "name", str(load_state))
            if state_name != "Loaded":
                self._collection.load()
                logger.info(f"Successfully loaded collection '{self.COLLECTION_NAME}'")
            else:
                logger.info(f"Collection '{self.COLLECTION_NAME}' already loaded")
        except AttributeError:
            # Method 2: try loading directly and catch already-loaded exception
            try:
                self._collection.load()
                logger.info(f"Successfully loaded collection '{self.COLLECTION_NAME}'")
            except MilvusException as e:
                error_msg = str(e).lower()
                if "already loaded" in error_msg or "loaded" in error_msg:
                    logger.info(f"Collection '{self.COLLECTION_NAME}' already loaded")
                else:
                    raise
        except Exception as e:
            logger.error(f"Failed to load collection: {e}")
            raise

    def get_collection(self) -> Collection:
        """
        Get collection instance

        Returns:
            Collection: collection instance

        Raises:
            RuntimeError: Raised when collection is not initialized
        """
        if self._collection is None:
            raise RuntimeError("Collection is not initialized; call connect() first")
        return self._collection

    def health_check(self) -> bool:
        """
        Health check

        Returns:
            bool: True means healthy, False means unhealthy
        """
        try:
            if self._client is None:
                return False

            # Try listing connections
            _ = connections.list_connections()
            return True

        except (MilvusException, ConnectionError) as e:
            logger.error(f"Milvus health check failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Milvus health check failed: {e}")
            return False

    def close(self) -> None:
        """Close connection"""
        errors = []
        
        try:
            if self._collection is not None:
                self._collection.release()
                self._collection = None
        except Exception as e:
            errors.append(f"Failed to release collection: {e}")

        try:
            if connections.has_connection("default"):
                connections.disconnect("default")
        except Exception as e:
            errors.append(f"Failed to disconnect: {e}")

        self._client = None
        
        if errors:
            error_msg = "; ".join(errors)
            logger.error(f"Error while closing Milvus connection: {error_msg}")
        else:
            logger.info("Milvus connection closed")

    def __enter__(self) -> "MilvusClientManager":
        """Context manager entry"""
        _ = self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object
    ) -> None:
        """Context manager exit"""
        self.close()


# Global singleton
milvus_manager = MilvusClientManager()
