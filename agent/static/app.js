// SuperBizAgent frontend app
class SuperBizAgentApp {
    constructor() {
        this.apiBaseUrl = 'http://localhost:9900/api';
        this.currentMode = 'quick'; // 'quick' or 'stream'
        this.sessionId = this.generateSessionId();
        this.isStreaming = false;
        this.currentChatHistory = []; // Message history for the current chat
        this.chatHistories = this.loadChatHistories(); // All chat histories
        this.isCurrentChatFromHistory = false; // Whether the current chat was loaded from history
        
        this.initializeElements();
        this.bindEvents();
        this.updateUI();
        this.initMarkdown();
        this.checkAndSetCentered();
        this.renderChatHistory();
    }

    // Initialize Markdown configuration
    initMarkdown() {
        // Wait for the marked library to load
        const checkMarked = () => {
            if (typeof marked !== 'undefined') {
                try {
                    // Configure marked options
                    marked.setOptions({
                        breaks: true,  // Support GFM line breaks
                        gfm: true,     // Enable GitHub-flavored Markdown
                        headerIds: false,
                        mangle: false
                    });

                    // Configure code highlighting
                    if (typeof hljs !== 'undefined') {
                        marked.setOptions({
                            highlight: function(code, lang) {
                                if (lang && hljs.getLanguage(lang)) {
                                    try {
                                        return hljs.highlight(code, { language: lang }).value;
                                    } catch (err) {
                                        console.error('Code highlighting failed:', err);
                                    }
                                }
                                return code;
                            }
                        });
                    }
                    console.log('Markdown rendering library initialized successfully');
                } catch (e) {
                    console.error('Markdown configuration failed:', e);
                }
            } else {
                // If marked is not loaded yet, retry after a short delay
                setTimeout(checkMarked, 100);
            }
        };
        checkMarked();
    }

    // Safely render Markdown
    renderMarkdown(content) {
        if (!content) return '';
        
        // Check whether marked is available
        if (typeof marked === 'undefined') {
            console.warn('marked library not loaded; displaying plain text');
            return this.escapeHtml(content);
        }
        
        try {
            const html = marked.parse(content);
            return html;
        } catch (e) {
            console.error('Markdown rendering failed:', e);
            return this.escapeHtml(content);
        }
    }

    // Highlight code blocks
    highlightCodeBlocks(container) {
        if (typeof hljs !== 'undefined' && container) {
            try {
                container.querySelectorAll('pre code').forEach((block) => {
                    if (!block.classList.contains('hljs')) {
                        hljs.highlightElement(block);
                    }
                });
            } catch (e) {
                console.error('Code highlighting failed:', e);
            }
        }
    }

    // Initialize DOM elements
    initializeElements() {
        // Sidebar elements
        this.sidebar = document.querySelector('.sidebar');
        this.newChatBtn = document.getElementById('newChatBtn');
        this.aiOpsSidebarBtn = document.getElementById('aiOpsSidebarBtn');
        
        // Input area elements
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.toolsBtn = document.getElementById('toolsBtn');
        this.toolsMenu = document.getElementById('toolsMenu');
        this.uploadFileItem = document.getElementById('uploadFileItem');
        this.modeSelectorBtn = document.getElementById('modeSelectorBtn');
        this.modeDropdown = document.getElementById('modeDropdown');
        this.currentModeText = document.getElementById('currentModeText');
        this.fileInput = document.getElementById('fileInput');
        
        // Chat area elements
        this.chatMessages = document.getElementById('chatMessages');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.chatContainer = document.querySelector('.chat-container');
        this.welcomeGreeting = document.getElementById('welcomeGreeting');
        this.chatHistoryList = document.getElementById('chatHistoryList');
        
        // Check whether centering is needed on initialization
        this.checkAndSetCentered();
    }

    // Bind event listeners
    bindEvents() {
        // New chat
        if (this.newChatBtn) {
            this.newChatBtn.addEventListener('click', () => this.newChat());
        }
        
        // AI Ops button
        if (this.aiOpsSidebarBtn) {
            this.aiOpsSidebarBtn.addEventListener('click', () => this.triggerAIOps());
        }
        
        // Mode selector dropdown
        if (this.modeSelectorBtn) {
            this.modeSelectorBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleModeDropdown();
            });
        }
        
        // Dropdown item click
        const dropdownItems = document.querySelectorAll('.dropdown-item');
        dropdownItems.forEach(item => {
            item.addEventListener('click', (e) => {
                const mode = item.getAttribute('data-mode');
                this.selectMode(mode);
                this.closeModeDropdown();
            });
        });
        
        // Click outside to close dropdown
        document.addEventListener('click', (e) => {
            if (!this.modeSelectorBtn.contains(e.target) && 
                !this.modeDropdown.contains(e.target)) {
                this.closeModeDropdown();
            }
        });
        
        // Send message
        if (this.sendButton) {
            this.sendButton.addEventListener('click', () => this.sendMessage());
        }
        
        if (this.messageInput) {
            this.messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
        }
        
        // Tools button and menu
        if (this.toolsBtn) {
            this.toolsBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleToolsMenu();
            });
        }
        
        // Tool menu item click event
        if (this.uploadFileItem) {
            this.uploadFileItem.addEventListener('click', () => {
                if (this.fileInput) {
                    this.fileInput.click();
                }
                this.closeToolsMenu();
            });
        }
        
        // Click outside to close tools menu
        document.addEventListener('click', (e) => {
            if (this.toolsBtn && this.toolsMenu && 
                !this.toolsBtn.contains(e.target) && 
                !this.toolsMenu.contains(e.target)) {
                this.closeToolsMenu();
            }
        });
        
        if (this.fileInput) {
            this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        }
    }

    // Toggle tools menu visibility
    toggleToolsMenu() {
        if (this.toolsMenu && this.toolsBtn) {
            const wrapper = this.toolsBtn.closest('.tools-btn-wrapper');
            if (wrapper) {
                wrapper.classList.toggle('active');
            }
        }
    }

    // Close tools menu
    closeToolsMenu() {
        if (this.toolsMenu && this.toolsBtn) {
            const wrapper = this.toolsBtn.closest('.tools-btn-wrapper');
            if (wrapper) {
                wrapper.classList.remove('active');
            }
        }
    }

    // New chat
    newChat() {
        if (this.isStreaming) {
            this.showNotification('Please wait for the current chat to finish before starting a new one', 'warning');
            return;
        }
        
        // If the current chat has content and was not loaded from history, save it as a new history item
        // If it was loaded from history, only update that history item
        if (this.currentChatHistory.length > 0) {
            if (this.isCurrentChatFromHistory) {
                // Current chat was loaded from history; update that history item
                this.updateCurrentChatHistory();
            } else {
                // Current chat is new; save it as a new history item
                this.saveCurrentChat();
            }
        }
        
        // Stop all in-progress operations
        this.isStreaming = false;
        
        // Clear input
        if (this.messageInput) {
            this.messageInput.value = '';
        }
        
        // Clear current chat history
        this.currentChatHistory = [];
        
        // Reset marker
        this.isCurrentChatFromHistory = false;
        
        // Clear chat messages
        if (this.chatMessages) {
            this.chatMessages.innerHTML = '';
        }
        
        // Generate a new session ID
        this.sessionId = this.generateSessionId();
        
        // Reset mode to quick
        this.currentMode = 'quick';
        this.updateUI();
        
        // Reset centering style so the chat box is centered
        this.checkAndSetCentered();
        
        // Ensure the container has a transition animation
        if (this.chatContainer) {
            this.chatContainer.style.transition = 'all 0.5s ease';
        }
        
        // Update chat history list
        this.renderChatHistory();
    }
    
    // Save current chat to history as new item
    saveCurrentChat() {
        if (this.currentChatHistory.length === 0) {
            return;
        }
        
        // Check whether a history item with the same ID already exists
        const existingIndex = this.chatHistories.findIndex(h => h.id === this.sessionId);
        if (existingIndex !== -1) {
            // If it exists, update instead of creating a new one
            this.updateCurrentChatHistory();
            return;
        }
        
        // Get chat title from the first 30 characters of the first user message
        const firstUserMessage = this.currentChatHistory.find(msg => msg.type === 'user');
        const title = firstUserMessage ? 
            (firstUserMessage.content.substring(0, 30) + (firstUserMessage.content.length > 30 ? '...' : '')) : 
            'New Chat';
        
        const chatHistory = {
            id: this.sessionId,
            title: title,
            messages: [...this.currentChatHistory],
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };
        
        // Add to the beginning of the history list
        this.chatHistories.unshift(chatHistory);
        
        // Limit history count to at most 50 items
        if (this.chatHistories.length > 50) {
            this.chatHistories = this.chatHistories.slice(0, 50);
        }
        
        // Save to localStorage
        this.saveChatHistories();
    }
    
    // Update the history item for the current chat
    updateCurrentChatHistory() {
        if (this.currentChatHistory.length === 0) {
            return;
        }
        
        const existingIndex = this.chatHistories.findIndex(h => h.id === this.sessionId);
        if (existingIndex === -1) {
            // If it does not exist, call the save method
            this.saveCurrentChat();
            return;
        }
        
        // Update existing history item
        const history = this.chatHistories[existingIndex];
        history.messages = [...this.currentChatHistory];
        history.updatedAt = new Date().toISOString();
        
        // Update title if needed because the first message changed
        const firstUserMessage = this.currentChatHistory.find(msg => msg.type === 'user');
        if (firstUserMessage) {
            const newTitle = firstUserMessage.content.substring(0, 30) + (firstUserMessage.content.length > 30 ? '...' : '');
            if (history.title !== newTitle) {
                history.title = newTitle;
            }
        }
        
        // Save to localStorage
        this.saveChatHistories();
    }
    
    // Load chat history list
    loadChatHistories() {
        try {
            const stored = localStorage.getItem('chatHistories');
            return stored ? JSON.parse(stored) : [];
        } catch (e) {
            console.error('Failed to load chat history:', e);
            return [];
        }
    }
    
    // Save chat history list to localStorage
    saveChatHistories() {
        try {
            localStorage.setItem('chatHistories', JSON.stringify(this.chatHistories));
        } catch (e) {
            console.error('Failed to save chat history:', e);
        }
    }
    
    // Render chat history list
    renderChatHistory() {
        if (!this.chatHistoryList) {
            return;
        }
        
        this.chatHistoryList.innerHTML = '';
        
        if (this.chatHistories.length === 0) {
            return;
        }
        
        this.chatHistories.forEach((history, index) => {
            const historyItem = document.createElement('div');
            historyItem.className = 'history-item';
            historyItem.dataset.historyId = history.id;
            
            historyItem.innerHTML = `
                <div class="history-item-content">
                    <span class="history-item-title">${this.escapeHtml(history.title)}</span>
                </div>
                <button class="history-item-delete" data-history-id="${history.id}" title="Delete">
                    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                </button>
            `;
            
            // Click a history item to load chat
            historyItem.addEventListener('click', (e) => {
                if (!e.target.closest('.history-item-delete')) {
                    this.loadChatHistory(history.id);
                }
            });
            
            // Delete chat history
            const deleteBtn = historyItem.querySelector('.history-item-delete');
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.confirmDeleteChatHistory(history.id);
            });
            
            this.chatHistoryList.appendChild(historyItem);
        });
    }
    
    // Load chat history
    async loadChatHistory(historyId) {
        const history = this.chatHistories.find(h => h.id === historyId);
        if (!history) {
            return;
        }
        
        // If the current chat has content and is not the same chat, save it first
        if (this.currentChatHistory.length > 0 && this.sessionId !== historyId) {
            if (this.isCurrentChatFromHistory) {
                // If current chat was also loaded from history, update it
                this.updateCurrentChatHistory();
            } else {
                // If current chat is new, save it as new history
                this.saveCurrentChat();
            }
        }
        
        try {
            // Fetch session history from backend
            const response = await fetch(`/api/chat/session/${historyId}`);
            if (response.ok) {
                const data = await response.json();
                const backendHistory = data.history || [];
                
                // Update session ID
                this.sessionId = history.id;
                this.isCurrentChatFromHistory = true;
                
                // Clear and rerender messages
                if (this.chatMessages) {
                    this.chatMessages.innerHTML = '';
                    
                    // Use backend history if available
                    if (backendHistory.length > 0) {
                        this.currentChatHistory = [];
                        backendHistory.forEach(msg => {
                            // Backend return format: {role: "user|assistant", content: "...", timestamp: "..."}
                            const messageType = msg.role === 'user' ? 'user' : 'bot';
                            this.addMessage(messageType, msg.content, false, false);
                        });
                    } else {
                        // Otherwise use localStorage history
                        this.currentChatHistory = [...history.messages];
                        history.messages.forEach(msg => {
                            this.addMessage(msg.type, msg.content, false, false);
                        });
                    }
                }
            } else {
                // If backend request fails, use localStorage history
                console.warn('Failed to load history from backend; using local cache');
                this.sessionId = history.id;
                this.currentChatHistory = [...history.messages];
                this.isCurrentChatFromHistory = true;
                
                if (this.chatMessages) {
                    this.chatMessages.innerHTML = '';
                    history.messages.forEach(msg => {
                        this.addMessage(msg.type, msg.content, false, false);
                    });
                }
            }
        } catch (error) {
            console.error('Failed to load session history:', error);
            // Use localStorage history when an error occurs
            this.sessionId = history.id;
            this.currentChatHistory = [...history.messages];
            this.isCurrentChatFromHistory = true;
            
            if (this.chatMessages) {
                this.chatMessages.innerHTML = '';
                history.messages.forEach(msg => {
                    this.addMessage(msg.type, msg.content, false, false);
                });
            }
        }
        
        // Update UI
        this.checkAndSetCentered();
        this.renderChatHistory();
    }
    
    // Confirm chat history deletion
    async confirmDeleteChatHistory(historyId) {
        const shouldDelete = await this.showConfirmDialog({
            title: 'Delete Conversation',
            message: 'This conversation will be permanently removed from your chat history.',
            confirmText: 'Delete',
            cancelText: 'Cancel',
            danger: true
        });

        if (shouldDelete) {
            await this.deleteChatHistory(historyId);
        }
    }

    // Delete chat history
    async deleteChatHistory(historyId) {
        try {
            // Call backend API to clear session
            const response = await fetch('/api/chat/clear', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: historyId
                })
            });

            if (!response.ok) {
                throw new Error('Failed to clear session');
            }

            const result = await response.json();
            
            if (result.status === 'success') {
                // Delete from local storage
                this.chatHistories = this.chatHistories.filter(h => h.id !== historyId);
                this.saveChatHistories();
                this.renderChatHistory();
                
                // If deleting the current chat, clear it
                if (this.sessionId === historyId) {
                    this.currentChatHistory = [];
                    if (this.chatMessages) {
                        this.chatMessages.innerHTML = '';
                    }
                    this.sessionId = this.generateSessionId();
                    this.checkAndSetCentered();
                }
                
                this.showNotification('Session cleared', 'success');
            } else {
                throw new Error(result.message || 'Failed to clear session');
            }
        } catch (error) {
            console.error('Failed to delete chat history:', error);
            this.showNotification('Delete failed: ' + error.message, 'error');
        }
    }

    // Show an in-app confirmation dialog instead of the browser native popup
    showConfirmDialog({ title, message, confirmText = 'Confirm', cancelText = 'Cancel', danger = false }) {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'confirm-dialog-overlay';
            overlay.innerHTML = `
                <div class="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirmDialogTitle">
                    <div class="confirm-dialog-title" id="confirmDialogTitle">${this.escapeHtml(title)}</div>
                    <div class="confirm-dialog-message">${this.escapeHtml(message)}</div>
                    <div class="confirm-dialog-actions">
                        <button class="confirm-dialog-btn secondary" type="button">${this.escapeHtml(cancelText)}</button>
                        <button class="confirm-dialog-btn ${danger ? 'danger' : 'primary'}" type="button">${this.escapeHtml(confirmText)}</button>
                    </div>
                </div>
            `;

            const cleanup = (result) => {
                document.removeEventListener('keydown', onKeyDown);
                overlay.remove();
                resolve(result);
            };

            const onKeyDown = (event) => {
                if (event.key === 'Escape') {
                    cleanup(false);
                }
            };

            overlay.addEventListener('click', (event) => {
                if (event.target === overlay) {
                    cleanup(false);
                }
            });

            const cancelBtn = overlay.querySelector('.confirm-dialog-btn.secondary');
            const confirmBtn = overlay.querySelector('.confirm-dialog-btn.danger, .confirm-dialog-btn.primary');

            cancelBtn.addEventListener('click', () => cleanup(false));
            confirmBtn.addEventListener('click', () => cleanup(true));
            document.addEventListener('keydown', onKeyDown);
            document.body.appendChild(overlay);
            confirmBtn.focus();
        });
    }

    // Toggle mode dropdown
    toggleModeDropdown() {
        if (this.modeSelectorBtn && this.modeDropdown) {
            const wrapper = this.modeSelectorBtn.closest('.mode-selector-wrapper');
            if (wrapper) {
                wrapper.classList.toggle('active');
            }
        }
    }

    // Close mode dropdown
    closeModeDropdown() {
        if (this.modeSelectorBtn && this.modeDropdown) {
            const wrapper = this.modeSelectorBtn.closest('.mode-selector-wrapper');
            if (wrapper) {
                wrapper.classList.remove('active');
            }
        }
    }

    // Select mode
    selectMode(mode) {
        if (this.isStreaming) {
            this.showNotification('Please wait for the current chat to finish before switching modes', 'warning');
            return;
        }
        
        this.currentMode = mode;
        this.updateUI();
        
        const modeNames = {
            'quick': 'Quick',
            'stream': 'Streaming'
        };
        
        this.showNotification(`Switched to ${modeNames[mode]} mode`, 'info');
    }

    // Update UI
    updateUI() {
        // Update mode selector display
        if (this.currentModeText) {
            const modeNames = {
                'quick': 'Quick',
                'stream': 'Streaming'
            };
            this.currentModeText.textContent = modeNames[this.currentMode] || 'Quick';
        }
        
        // Update selected dropdown state
        const dropdownItems = document.querySelectorAll('.dropdown-item');
        dropdownItems.forEach(item => {
            const mode = item.getAttribute('data-mode');
            if (mode === this.currentMode) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
        
        // Update send button state
        if (this.sendButton) {
            this.sendButton.disabled = this.isStreaming;
        }
        
        // Update input state
        if (this.messageInput) {
            this.messageInput.disabled = this.isStreaming;
            this.messageInput.placeholder = 'Ask the Smart OnCall assistant';
        }
    }

    // Generate random session ID
    generateSessionId() {
        return 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
    }

    // Send message
    async sendMessage() {
        let message = '';
        if (this.messageInput) {
            message = this.messageInput.value.trim();
        }
        
        if (!message) {
            this.showNotification('Please enter a message', 'warning');
            return;
        }

        if (this.isStreaming) {
            this.showNotification('Please wait for the current chat to finish', 'warning');
            return;
        }

        // Show user message
        this.addMessage('user', message);
        
        // Clear input
        if (this.messageInput) {
            this.messageInput.value = '';
        }

        // Set sending state
        this.isStreaming = true;
        this.updateUI();

        try {
            if (this.currentMode === 'quick') {
                await this.sendQuickMessage(message);
            } else if (this.currentMode === 'stream') {
                await this.sendStreamMessage(message);
            }
        } catch (error) {
            console.error('Failed to send message:', error);
            this.addMessage('assistant', 'Sorry, an error occurred while sending the message: ' + error.message);
        } finally {
            this.isStreaming = false;
            this.updateUI();
            
            // If current chat was loaded from history, update the history item
            if (this.isCurrentChatFromHistory && this.currentChatHistory.length > 0) {
                this.updateCurrentChatHistory();
                this.renderChatHistory(); // Update chat history list display
            }
        }
    }

    // Send quick message (normal chat)
    async sendQuickMessage(message) {
        // Add waiting message
        const loadingMessage = this.addLoadingMessage('Thinking...');
        
        try {
            const response = await fetch(`${this.apiBaseUrl}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    Id: this.sessionId,
                    Question: message
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error: ${response.status}`);
            }

            const data = await response.json();
            console.log('[sendQuickMessage] response data:', JSON.stringify(data));
            
            // Remove waiting message
            if (loadingMessage && loadingMessage.parentNode) {
                loadingMessage.parentNode.removeChild(loadingMessage);
            }
            
            // Unified response format: check data.code or data.message to determine success
            if (data.code === 200 || data.message === 'success') {
                // data.data is a ChatResponse object
                const chatResponse = data.data;
                
                if (chatResponse && chatResponse.success) {
                    // Success: add actual response message, even if answer is empty
                    const answer = chatResponse.answer || '(No response content)';
                    this.addMessage('assistant', answer);
                } else if (chatResponse && chatResponse.errorMessage) {
                    // Business error
                    throw new Error(chatResponse.errorMessage);
                } else {
                    // Fallback: try to display any available content
                    const fallbackAnswer = chatResponse?.answer || chatResponse?.errorMessage || 'Service returned empty content';
                    this.addMessage('assistant', fallbackAnswer);
                }
            } else {
                // HTTP succeeded but business logic failed; prefer backend error details
                const apiErrorMessage = data?.data?.errorMessage || data?.message || 'Request failed';
                throw new Error(apiErrorMessage);
            }
        } catch (error) {
            // Remove waiting message on error too
            if (loadingMessage && loadingMessage.parentNode) {
                loadingMessage.parentNode.removeChild(loadingMessage);
            }
            throw error;
        }
    }

    // Send streaming message
    async sendStreamMessage(message) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/chat_stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    Id: this.sessionId,
                    Question: message
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error: ${response.status}`);
            }
            
            // Create assistant message element
            const assistantMessageElement = this.addMessage('assistant', '', true);
            let fullResponse = '';

            // Handle streaming response
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let currentEvent = '';

            try {
                while (true) {
                    const { done, value } = await reader.read();
                    
                    if (done) {
                        // Stream ended; use unified handler
                        this.handleStreamComplete(assistantMessageElement, fullResponse);
                        break;
                    }

                    // Decode data and append to buffer
                    buffer += decoder.decode(value, { stream: true });
                    
                    // Split and process by line
                    const lines = buffer.split('\n');
                    // Keep the last line, which may be incomplete
                    buffer = lines.pop() || '';
                    
                    for (const line of lines) {
                        if (line.trim() === '') continue;
                        
                        console.log('[SSE debug] received line:', line);
                        
                        // Parse SSE format
                        if (line.startsWith('id:')) {
                            console.log('[SSE debug] Parsed ID');
                            continue;
                        } else if (line.startsWith('event:')) {
                            // Support both "event:message" and "event: message" formats
                            currentEvent = line.substring(6).trim();
                            console.log('[SSE debug] Parsed event type:', currentEvent);
                            // Note: backend uses the unified "message" event name; actual type is in data JSON
                            continue;
                        } else if (line.startsWith('data:')) {
                            // Support both "data:xxx" and "data: xxx" formats
                            const rawData = line.substring(5).trim();
                            console.log('[SSE debug] Parsed data, currentEvent:', currentEvent, ', rawData:', rawData);
                            
                            // Support legacy [DONE] marker
                            if (rawData === '[DONE]') {
                                // Stream end marker; render content as Markdown
                                this.handleStreamComplete(assistantMessageElement, fullResponse);
                                return;
                            }
                            
                            // Process SSE data
                            try {
                                // Try parsing JSON as SseMessage format
                                const sseMessage = JSON.parse(rawData);
                                console.log('[SSE debug] Parsed JSON successfully:', sseMessage);
                                
                                if (sseMessage && typeof sseMessage.type === 'string') {
                                    if (sseMessage.type === 'content') {
                                        const content = sseMessage.data || '';
                                        fullResponse += content;
                                        console.log('[SSE debug] Added content:', content);
                                        
                                        // Render Markdown in real time
                                        if (assistantMessageElement) {
                                            const messageContent = assistantMessageElement.querySelector('.message-content');
                                            messageContent.innerHTML = this.renderMarkdown(fullResponse);
                                            // Highlight code blocks
                                            this.highlightCodeBlocks(messageContent);
                                            this.scrollToBottom();
                                        }
                                    } else if (sseMessage.type === 'done') {
                                        console.log('[SSE debug] Received done marker; stream ended');
                                        this.handleStreamComplete(assistantMessageElement, fullResponse);
                                        return;
                                    } else if (sseMessage.type === 'error') {
                                        console.error('[SSE debug] Received error:', sseMessage.data);
                                        if (assistantMessageElement) {
                                            const messageContent = assistantMessageElement.querySelector('.message-content');
                                            messageContent.innerHTML = this.renderMarkdown('Error: ' + (sseMessage.data || 'Unknown error'));
                                        }
                                        return;
                                    }
                                } else {
                                    // Not standard SseMessage format; trying compatible handling
                                    console.log('[SSE debug] Non-standard format; trying compatible handling');
                                    fullResponse += rawData;
                                    if (assistantMessageElement) {
                                        const messageContent = assistantMessageElement.querySelector('.message-content');
                                        messageContent.innerHTML = this.renderMarkdown(fullResponse);
                                        this.highlightCodeBlocks(messageContent);
                                        this.scrollToBottom();
                                    }
                                }
                            } catch (e) {
                                // JSON parse failed; trying legacy-compatible mode
                                console.log('[SSE debug] JSON parse failed; using compatible mode:', e.message);
                                if (rawData === '') {
                                    fullResponse += '\n';
                                } else {
                                    fullResponse += rawData;
                                }
                                
                                if (assistantMessageElement) {
                                    const messageContent = assistantMessageElement.querySelector('.message-content');
                                    messageContent.innerHTML = this.renderMarkdown(fullResponse);
                                    this.highlightCodeBlocks(messageContent);
                                    this.scrollToBottom();
                                }
                            }
                        }
                    }
                }
            } finally {
                reader.releaseLock();
            }
        } catch (error) {
            throw error;
        }
    }

    // Add message to chat UI
    addMessage(type, content, isStreaming = false, saveToHistory = true) {
        // Check if this is the first message; remove centered style if so
        const isFirstMessage = this.chatMessages && this.chatMessages.querySelectorAll('.message').length === 0;
        
        // Save message to current chat history if not streaming and save is needed
        if (!isStreaming && saveToHistory && content) {
            this.currentChatHistory.push({
                type: type,
                content: content,
                timestamp: new Date().toISOString()
            });
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}${isStreaming ? ' streaming' : ''}`;

        // Add avatar icon for assistant messages
        if (type === 'assistant') {
            const messageAvatar = document.createElement('div');
            messageAvatar.className = 'message-avatar';
            messageAvatar.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="white"/>
                </svg>
            `;
            messageDiv.appendChild(messageAvatar);
        }

        // Create message content wrapper
        const messageContentWrapper = document.createElement('div');
        messageContentWrapper.className = 'message-content-wrapper';

        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        // Render assistant non-streaming messages as Markdown
        if (type === 'assistant' && !isStreaming) {
            messageContent.innerHTML = this.renderMarkdown(content);
            // Highlight code blocks
            this.highlightCodeBlocks(messageContent);
        } else {
            // Use plain text for user or streaming messages
            messageContent.textContent = content;
        }

        messageContentWrapper.appendChild(messageContent);
        messageDiv.appendChild(messageContentWrapper);

        if (this.chatMessages) {
            this.chatMessages.appendChild(messageDiv);
            
            // If this is the first message, remove centered style and add animation
            if (isFirstMessage && this.chatContainer) {
                this.chatContainer.classList.remove('centered');
                // Add animation class
                this.chatContainer.style.transition = 'all 0.5s ease';
            }
            
            this.scrollToBottom();
        }

        return messageDiv;
    }

    // Add message with loading animation
    addLoadingMessage(content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant';

        // Add avatar icon
        const messageAvatar = document.createElement('div');
        messageAvatar.className = 'message-avatar';
        messageAvatar.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="white"/>
            </svg>
        `;
        messageDiv.appendChild(messageAvatar);

        // Create message content wrapper
        const messageContentWrapper = document.createElement('div');
        messageContentWrapper.className = 'message-content-wrapper';

        const messageContent = document.createElement('div');
        messageContent.className = 'message-content loading-message-content';
        
        // Create text and animation container
        const textSpan = document.createElement('span');
        textSpan.textContent = content;
        
        // Create spinning icon
        const loadingIcon = document.createElement('span');
        loadingIcon.className = 'loading-spinner-icon';
        loadingIcon.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z" fill="currentColor" opacity="0.2"/>
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10c1.54 0 3-.36 4.28-1l-1.5-2.6C13.64 19.62 12.84 20 12 20c-4.41 0-8-3.59-8-8s3.59-8 8-8c.84 0 1.64.38 2.18 1l1.5-2.6C13 2.36 12.54 2 12 2z" fill="currentColor"/>
            </svg>
        `;
        
        messageContent.appendChild(textSpan);
        messageContent.appendChild(loadingIcon);
        messageContentWrapper.appendChild(messageContent);
        messageDiv.appendChild(messageContentWrapper);

        if (this.chatMessages) {
            this.chatMessages.appendChild(messageDiv);
            
            // If this is the first message, remove centered style
            const isFirstMessage = this.chatMessages.querySelectorAll('.message').length === 1;
            if (isFirstMessage && this.chatContainer) {
                this.chatContainer.classList.remove('centered');
                this.chatContainer.style.transition = 'all 0.5s ease';
            }
            
            this.scrollToBottom();
        }

        return messageDiv;
    }
    
    // Check and set centered style
    checkAndSetCentered() {
        if (this.chatMessages && this.chatContainer) {
            const hasMessages = this.chatMessages.querySelectorAll('.message').length > 0;
            if (!hasMessages) {
                this.chatContainer.classList.add('centered');
            } else {
                this.chatContainer.classList.remove('centered');
            }
        }
    }

    // Scroll to bottom
    scrollToBottom() {
        if (this.chatMessages) {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }
    }

    // Handle stream completion
    handleStreamComplete(assistantMessageElement, fullResponse) {
        if (assistantMessageElement) {
            assistantMessageElement.classList.remove('streaming');
            const messageContent = assistantMessageElement.querySelector('.message-content');
            if (messageContent) {
                messageContent.innerHTML = this.renderMarkdown(fullResponse);
                // Highlight code blocks
                this.highlightCodeBlocks(messageContent);
            }
        }
        // Save streaming message to history
        if (fullResponse) {
            this.currentChatHistory.push({
                type: 'assistant',
                content: fullResponse,
                timestamp: new Date().toISOString()
            });
            // If current chat was loaded from history, update the history item
            if (this.isCurrentChatFromHistory) {
                this.updateCurrentChatHistory();
                this.renderChatHistory();
            }
        }
    }

    // Show notification
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            z-index: 10000;
            animation: slideIn 0.3s ease;
            max-width: 300px;
        `;

        // Set color by type using Google Material Design palette
        const colors = {
            info: '#1a73e8',
            success: '#34a853',
            warning: '#fbbc04',
            error: '#ea4335'
        };
        notification.style.backgroundColor = colors[type] || colors.info;

        // Add to page
        document.body.appendChild(notification);

        // Auto-remove after 3 seconds
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }

    // Handle file selection
    handleFileSelect(event) {
        const file = event.target.files[0];
        if (file) {
            // Validate file format
            if (!this.validateFileType(file)) {
                this.showNotification('Only TXT or Markdown (.md) files are supported', 'error');
                this.fileInput.value = '';
                return;
            }
            this.uploadFile(file);
        }
    }

    // Validate file type
    validateFileType(file) {
        const fileName = file.name.toLowerCase();
        const allowedExtensions = ['.txt', '.md', '.markdown'];
        return allowedExtensions.some(ext => fileName.endsWith(ext));
    }

    // Upload file to knowledge base
    async uploadFile(file) {
        // Validate file type again as a safety check
        if (!this.validateFileType(file)) {
            this.showNotification('Only TXT or Markdown (.md) files are supported', 'error');
            return;
        }

        // Validate file size, limited to 50 MB
        const maxSize = 50 * 1024 * 1024;
        if (file.size > maxSize) {
            this.showNotification('File size cannot exceed 50 MB', 'error');
            return;
        }

        // Lock the frontend and show upload overlay
        this.isStreaming = true;
        this.updateUI();
        this.showUploadOverlay(true, file.name);

        try {
            // Create FormData
            const formData = new FormData();
            formData.append('file', file);

            // Send upload request
            const response = await fetch(`${this.apiBaseUrl}/upload`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`HTTP error: ${response.status}`);
            }

            const data = await response.json();

            if ((data.code === 200 || data.message === 'success') && data.data) {
                // Show upload success message in the chat UI
                const successMessage = `${file.name} uploaded to the knowledge base successfully`;
                this.addMessage('assistant', successMessage, false, true);
            } else {
                throw new Error(data.message || 'Upload failed');
            }
        } catch (error) {
            console.error('File upload failed:', error);
            this.showNotification('File upload failed: ' + error.message, 'error');
        } finally {
            // Clear file input
            if (this.fileInput) {
                this.fileInput.value = '';
            }
            // Unlock frontend
            this.isStreaming = false;
            this.showUploadOverlay(false);
            this.updateUI();
        }
    }

    // Format file size
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }

    // Send AIOps request in SSE streaming mode
    async sendAIOpsRequest(loadingMessageElement) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/aiops`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.sessionId
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error: ${response.status}`);
            }

            let fullResponse = '';

            // Handle SSE streaming response
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let currentEvent = 'message'; // Default event type is message

            try {
                while (true) {
                    const { done, value } = await reader.read();
                    
                    if (done) {
                        // Stream ended; update final content
                        if (fullResponse) {
                            console.log('AI Ops stream ended; updating final content, length:', fullResponse.length);
                            this.updateAIOpsMessage(loadingMessageElement, fullResponse, []);
                        }
                        break;
                    }

                    // Decode data and append to buffer
                    buffer += decoder.decode(value, { stream: true });
                    
                    // Split and process by line
                    const lines = buffer.split('\n');
                    // Keep the last line, which may be incomplete
                    buffer = lines.pop() || '';
                    
                    for (const line of lines) {
                        if (line.trim() === '') continue;
                        
                        console.log('[AI Ops SSE] Received line:', line);
                        
                        // Parse SSE format
                        if (line.startsWith('id:')) {
                            continue;
                        } else if (line.startsWith('event:')) {
                            currentEvent = line.substring(6).trim();
                            console.log('[AI Ops SSE] Event type:', currentEvent);
                            continue;
                        } else if (line.startsWith('data:')) {
                            const rawData = line.substring(5).trim();
                            console.log('[AI Ops SSE] Data:', rawData, ', currentEvent:', currentEvent);
                            
                            // Parse data that may contain multiple JSON objects
                            const processJsonMessages = (data) => {
                                const jsonPattern = /\{"type"\s*:\s*"[^"]+"\s*,\s*"data"\s*:\s*(?:"[^"]*"|null)\}/g;
                                const matches = data.match(jsonPattern);
                                
                                if (matches && matches.length > 0) {
                                    console.log('[AI Ops SSE] Matched', matches.length, 'JSON objects');
                                    for (const jsonStr of matches) {
                                        try {
                                            const sseMessage = JSON.parse(jsonStr);
                                            if (sseMessage.type === 'content') {
                                                fullResponse += sseMessage.data || '';
                                            } else if (sseMessage.type === 'plan') {
                                                // Handle plan creation event
                                                const planText = `\n\n## 📋 Execution Plan\n${sseMessage.message}\n\n`;
                                                fullResponse += planText;
                                            } else if (sseMessage.type === 'step_complete') {
                                                // Handle step completion event
                                                const stepText = `\n✅ ${sseMessage.message}\n`;
                                                fullResponse += stepText;
                                            } else if (sseMessage.type === 'status') {
                                                // Handle status update event
                                                const statusText = `\n⏳ ${sseMessage.message}\n`;
                                                fullResponse += statusText;
                                            } else if (sseMessage.type === 'report') {
                                                // Handle final report event - streaming output
                                                console.log('AI Ops final report generated');
                                                const reportText = `\n\n## 🎯 Diagnosis Report\n\n${sseMessage.report || ''}\n`;
                                                fullResponse += reportText;
                                            } else if (sseMessage.type === 'complete') {
                                                // Handle completion event
                                                console.log('AI Ops diagnosis completed');
                                                if (sseMessage.response) {
                                                    fullResponse += `\n\n${sseMessage.response}`;
                                                }
                                                this.updateAIOpsMessage(loadingMessageElement, fullResponse, []);
                                                return true;
                                            } else if (sseMessage.type === 'done') {
                                                console.log('AI Ops stream completed, final content length:', fullResponse.length);
                                                this.updateAIOpsMessage(loadingMessageElement, fullResponse, []);
                                                return true;
                                            } else if (sseMessage.type === 'error') {
                                                const error = new Error(sseMessage.data || sseMessage.message || 'AIOps analysis failed');
                                                error.isAIOpsStreamError = true;
                                                throw error;
                                            }
                                        } catch (e) {
                                            if (e.isAIOpsStreamError) throw e;
                                            console.log('[AI Ops SSE] Single JSON parse failed:', jsonStr);
                                        }
                                    }
                                    if (loadingMessageElement) {
                                        this.updateAIOpsStreamContent(loadingMessageElement, fullResponse);
                                    }
                                    return false;
                                }
                                return null;
                            };
                            
                            const result = processJsonMessages(rawData);
                            if (result === true) {
                                return; // Stream ended
                            } else if (result === null) {
                                // No multiple JSON objects matched; trying single JSON parse
                                try {
                                    const sseMessage = JSON.parse(rawData);
                                    if (sseMessage && sseMessage.type) {
                                        if (sseMessage.type === 'content') {
                                            fullResponse += sseMessage.data || '';
                                            if (loadingMessageElement) {
                                                this.updateAIOpsStreamContent(loadingMessageElement, fullResponse);
                                            }
                                        } else if (sseMessage.type === 'plan') {
                                            // Handle plan creation event
                                            const planText = `\n\n## 📋 Execution Plan\n${sseMessage.message}\n\n`;
                                            fullResponse += planText;
                                            if (loadingMessageElement) {
                                                this.updateAIOpsStreamContent(loadingMessageElement, fullResponse);
                                            }
                                        } else if (sseMessage.type === 'step_complete') {
                                            // Handle step completion event
                                            const stepText = `\n✅ ${sseMessage.message}\n`;
                                            fullResponse += stepText;
                                            if (loadingMessageElement) {
                                                this.updateAIOpsStreamContent(loadingMessageElement, fullResponse);
                                            }
                                        } else if (sseMessage.type === 'status') {
                                            // Handle status update event
                                            const statusText = `\n⏳ ${sseMessage.message}\n`;
                                            fullResponse += statusText;
                                            if (loadingMessageElement) {
                                                this.updateAIOpsStreamContent(loadingMessageElement, fullResponse);
                                            }
                                        } else if (sseMessage.type === 'report') {
                                            // Handle final report event - critical path
                                            console.log('AI Ops final report generated, streaming output...');
                                            const reportText = `\n\n## 🎯 Diagnosis Report\n\n${sseMessage.report || ''}\n`;
                                            fullResponse += reportText;
                                            if (loadingMessageElement) {
                                                this.updateAIOpsStreamContent(loadingMessageElement, fullResponse);
                                            }
                                        } else if (sseMessage.type === 'complete') {
                                            // Handle completion event
                                            console.log('AI Ops diagnosis completed, final content length:', fullResponse.length);
                                            if (sseMessage.response) {
                                                fullResponse += `\n\n${sseMessage.response}`;
                                            }
                                            // Update message with final full content
                                            this.updateAIOpsMessage(loadingMessageElement, fullResponse, []);
                                            return;
                                        } else if (sseMessage.type === 'done') {
                                            console.log('AI Ops stream completed, final content length:', fullResponse.length);
                                            this.updateAIOpsMessage(loadingMessageElement, fullResponse, []);
                                            return;
                                        } else if (sseMessage.type === 'error') {
                                            const error = new Error(sseMessage.data || sseMessage.message || 'AIOps analysis failed');
                                            error.isAIOpsStreamError = true;
                                            throw error;
                                        }
                                    } else {
                                        fullResponse += rawData;
                                        if (loadingMessageElement) {
                                            this.updateAIOpsStreamContent(loadingMessageElement, fullResponse);
                                        }
                                    }
                                } catch (e) {
                                    if (e.isAIOpsStreamError) throw e;
                                    // Non-JSON format; append raw data directly
                                    fullResponse += rawData;
                                    if (loadingMessageElement) {
                                        this.updateAIOpsStreamContent(loadingMessageElement, fullResponse);
                                    }
                                }
                            }
                        }
                    }
                }
            } finally {
                reader.releaseLock();
            }
        } catch (error) {
            throw error;
        }
    }

    // Update AIOps streaming content in real time
    updateAIOpsStreamContent(messageElement, content) {
        if (!messageElement) return;
        
        // Add aiops-message class
        messageElement.classList.add('aiops-message');
        
        const messageContentWrapper = messageElement.querySelector('.message-content-wrapper');
        if (messageContentWrapper) {
            let messageContent = messageContentWrapper.querySelector('.message-content');
            if (!messageContent) {
                messageContent = document.createElement('div');
                messageContent.className = 'message-content';
                messageContentWrapper.appendChild(messageContent);
            }
            // Use plain text during streaming display
            messageContent.textContent = content;
            this.scrollToBottom();
        }
    }

    // Update AIOps message with collapsible details
    updateAIOpsMessage(messageElement, response, details) {
        console.log('updateAIOpsMessage called');
        console.log('messageElement:', messageElement);
        console.log('response:', response);
        console.log('response length:', response ? response.length : 0);
        console.log('details:', details);
        
        if (!messageElement) {
            // Create a new message if no message element was provided
            console.log('messageElement is empty; creating new message');
            return this.addAIOpsMessage(response, details);
        }

        // Add aiops-message class
        messageElement.classList.add('aiops-message');

        // Get message content wrapper
        const messageContentWrapper = messageElement.querySelector('.message-content-wrapper');
        if (!messageContentWrapper) {
            console.error('message-content-wrapper not found');
            return;
        }

        // Clear existing content while keeping the message content container
        const messageContent = messageContentWrapper.querySelector('.message-content');
        if (!messageContent) {
            console.error('message-content not found');
            return;
        }

        // Remove loading animation classes and content
        messageContent.classList.remove('loading-message-content');
        messageContent.textContent = '';
        
        // Remove loading icon if present
        const loadingIcon = messageContent.querySelector('.loading-spinner-icon');
        if (loadingIcon) {
            loadingIcon.remove();
        }

        // Details section, collapsible, displayed first
        if (details && details.length > 0) {
            // Check whether details container already exists
            let detailsContainer = messageElement.querySelector('.aiops-details');
            if (!detailsContainer) {
                detailsContainer = document.createElement('div');
                detailsContainer.className = 'aiops-details';
                messageContentWrapper.insertBefore(detailsContainer, messageContent);
            } else {
                // Clear existing details
                detailsContainer.innerHTML = '';
            }

            const detailsToggle = document.createElement('div');
            detailsToggle.className = 'details-toggle';
            detailsToggle.innerHTML = `
                <svg class="toggle-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M9 18L15 12L9 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <span>View detailed steps (${details.length})</span>
            `;

            const detailsContent = document.createElement('div');
            detailsContent.className = 'details-content';
            
            details.forEach((detail, index) => {
                const detailItem = document.createElement('div');
                detailItem.className = 'detail-item';
                detailItem.innerHTML = `<strong>Step ${index + 1}:</strong> ${this.escapeHtml(detail)}`;
                detailsContent.appendChild(detailItem);
            });

            // Click to toggle collapsed state
            detailsToggle.addEventListener('click', () => {
                detailsContent.classList.toggle('expanded');
                detailsToggle.classList.toggle('expanded');
            });

            detailsContainer.appendChild(detailsToggle);
            detailsContainer.appendChild(detailsContent);
        }

        // Update main response content using Markdown rendering
        console.log('Starting Markdown rendering');
        const renderedHtml = this.renderMarkdown(response);
        console.log('Markdown rendering completed, HTML length:', renderedHtml ? renderedHtml.length : 0);
        messageContent.innerHTML = renderedHtml;
        console.log('innerHTML has been set');
        // Highlight code blocks
        this.highlightCodeBlocks(messageContent);
        console.log('Code block highlighting completed');
        
        // Save to history
        this.currentChatHistory.push({
            type: 'assistant',
            content: response,
            timestamp: new Date().toISOString()
        });
        
        this.scrollToBottom();
        return messageElement;
    }

    // Add AIOps message with collapsible details, kept for compatibility
    addAIOpsMessage(response, details) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant aiops-message';

        // Add avatar icon
        const messageAvatar = document.createElement('div');
        messageAvatar.className = 'message-avatar';
        messageAvatar.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="white"/>
            </svg>
        `;
        messageDiv.appendChild(messageAvatar);

        // Create message content wrapper
        const messageContentWrapper = document.createElement('div');
        messageContentWrapper.className = 'message-content-wrapper';

        // Details section, collapsible, displayed first
        if (details && details.length > 0) {
            const detailsContainer = document.createElement('div');
            detailsContainer.className = 'aiops-details';

            const detailsToggle = document.createElement('div');
            detailsToggle.className = 'details-toggle';
            detailsToggle.innerHTML = `
                <svg class="toggle-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M9 18L15 12L9 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <span>View detailed steps (${details.length})</span>
            `;

            const detailsContent = document.createElement('div');
            detailsContent.className = 'details-content';
            
            details.forEach((detail, index) => {
                const detailItem = document.createElement('div');
                detailItem.className = 'detail-item';
                detailItem.innerHTML = `<strong>Step ${index + 1}:</strong> ${this.escapeHtml(detail)}`;
                detailsContent.appendChild(detailItem);
            });

            // Click to toggle collapsed state
            detailsToggle.addEventListener('click', () => {
                detailsContent.classList.toggle('expanded');
                detailsToggle.classList.toggle('expanded');
            });

            detailsContainer.appendChild(detailsToggle);
            detailsContainer.appendChild(detailsContent);
            messageContentWrapper.appendChild(detailsContainer);
        }

        // Main response content, displayed after details, using Markdown rendering
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.innerHTML = this.renderMarkdown(response);
        // Highlight code blocks
        this.highlightCodeBlocks(messageContent);
        messageContentWrapper.appendChild(messageContent);
        messageDiv.appendChild(messageContentWrapper);
        
        if (this.chatMessages) {
            this.chatMessages.appendChild(messageDiv);
            this.scrollToBottom();
        }

        return messageDiv;
    }

    // HTML escaping
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Trigger AIOps, called directly when clicking the AIOps button
    async triggerAIOps() {
        if (this.isStreaming) {
            this.showNotification('Please wait for the current operation to finish', 'warning');
            return;
        }

        // New chat
        this.newChat();
        
        // Add an "Analyzing..." message with spinner animation
        const loadingMessage = this.addLoadingMessage('Analyzing...');
        this.currentAIOpsMessage = loadingMessage; // Save message reference for later updates
        
        // Set sending state
        this.isStreaming = true;
        this.updateUI();

        try {
            await this.sendAIOpsRequest(loadingMessage);
        } catch (error) {
            console.error('AIOps analysis failed:', error);
            // Update message with error information
            if (loadingMessage) {
                const messageContent = loadingMessage.querySelector('.message-content');
                if (messageContent) {
                    messageContent.textContent = 'Sorry, an error occurred during AIOps analysis: ' + error.message;
                }
            }
        } finally {
            this.isStreaming = false;
            this.currentAIOpsMessage = null;
            this.updateUI();
        }
    }

    // Show/hide loading overlay
    showLoadingOverlay(show) {
        if (this.loadingOverlay) {
            if (show) {
                this.loadingOverlay.style.display = 'flex';
                // Update text for AIOps
                const loadingText = this.loadingOverlay.querySelector('.loading-text');
                const loadingSubtext = this.loadingOverlay.querySelector('.loading-subtext');
                if (loadingText) loadingText.textContent = 'AIOps analysis in progress, please wait...';
                if (loadingSubtext) loadingSubtext.textContent = 'The backend is processing. Please wait.';
                // Prevent page scrolling
                document.body.style.overflow = 'hidden';
            } else {
                this.loadingOverlay.style.display = 'none';
                // Restore page scrolling
                document.body.style.overflow = '';
            }
        }
    }

    // Show/hide upload overlay
    showUploadOverlay(show, fileName = '') {
        if (this.loadingOverlay) {
            if (show) {
                this.loadingOverlay.style.display = 'flex';
                // Update text for upload state
                const loadingText = this.loadingOverlay.querySelector('.loading-text');
                const loadingSubtext = this.loadingOverlay.querySelector('.loading-subtext');
                if (loadingText) loadingText.textContent = 'Uploading file...';
                if (loadingSubtext) loadingSubtext.textContent = fileName ? `Uploading: ${fileName}` : 'Please wait';
                // Prevent page scrolling
                document.body.style.overflow = 'hidden';
            } else {
                this.loadingOverlay.style.display = 'none';
                // Restore page scrolling
                document.body.style.overflow = '';
            }
        }
    }
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    new SuperBizAgentApp();
});
