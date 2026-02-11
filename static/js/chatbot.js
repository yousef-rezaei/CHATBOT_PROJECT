/**
 * NORMAN SLE Chatbot Widget - FINAL FIX
 * Fixed: Double-sending messages from quick action buttons
 */

(function() {
    'use strict';

    // Prevent multiple initialization
    if (window.NormanChatbotInitialized) {
        console.log('⚠️ Chatbot already initialized, skipping...');
        return;
    }
    window.NormanChatbotInitialized = true;

    console.log('🤖 Chatbot script loaded');

    // Configuration
    const CONFIG = window.CHATBOT_CONFIG || {
        apiEndpoint: '/api/chatbot/message/',
        csrfToken: document.querySelector('[name=csrfmiddlewaretoken]')?.value || '',
    };

    // DOM Elements
    let elements = {};

    // State
    const state = {
        isOpen: false,
        isProcessing: false,
        messageHistory: [],
    };

    /**
     * Initialize the chatbot
     */
    function init() {
        console.log('🔧 Initializing chatbot...');
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initElements);
        } else {
            initElements();
        }
    }

    /**
     * Initialize DOM elements and event listeners
     */
    function initElements() {
        console.log('📦 Finding DOM elements...');
        
        elements = {
            chatbotToggle: document.getElementById('chatbotToggle'),
            chatbotContainer: document.getElementById('chatbotContainer'),
            chatbotClose: document.getElementById('chatbotClose'),
            chatbotMessages: document.getElementById('chatbotMessages'),
            chatbotInput: document.getElementById('chatbotInput'),
            chatbotSend: document.getElementById('chatbotSend'),
            typingIndicator: document.getElementById('typingIndicator'),
            chatIcon: document.getElementById('chatIcon'),
            closeIcon: document.getElementById('closeIcon'),
            quickActionBtns: document.querySelectorAll('.quick-action-btn'),
        };

        // Verify all elements exist
        let allFound = true;
        for (const [key, element] of Object.entries(elements)) {
            if (!element && key !== 'quickActionBtns') {
                console.error(`❌ Element not found: ${key}`);
                allFound = false;
            }
        }

        if (!allFound) {
            console.error('❌ Some chatbot elements are missing from the page!');
            return;
        }

        console.log('✅ All elements found, attaching listeners...');
        attachEventListeners();
        scrollToBottom();
        console.log('✅ Chatbot ready!');
    }

    /**
     * Attach all event listeners
     */
    function attachEventListeners() {
        // Toggle chatbot
        if (elements.chatbotToggle) {
            elements.chatbotToggle.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                console.log('🖱️ Toggle button clicked');
                toggleChatbot();
            });
        }

        if (elements.chatbotClose) {
            elements.chatbotClose.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                console.log('🖱️ Close button clicked');
                toggleChatbot();
            });
        }

        // Auto-resize textarea
        if (elements.chatbotInput) {
            elements.chatbotInput.addEventListener('input', autoResizeTextarea);
            
            // Send message on Enter (Shift+Enter for new line)
            elements.chatbotInput.addEventListener('keydown', handleInputKeydown);
        }

        // Send button click
        if (elements.chatbotSend) {
            elements.chatbotSend.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                sendMessage();
            });
        }

        // Quick action buttons - FIXED: Prevent double event listeners
        if (elements.quickActionBtns && elements.quickActionBtns.length > 0) {
            console.log(`📌 Attaching ${elements.quickActionBtns.length} quick action listeners`);
            
            elements.quickActionBtns.forEach((btn, index) => {
                // Check if already has listener
                if (btn.dataset.listenerAttached === 'true') {
                    console.log(`⏭️ Button ${index} already has listener, skipping`);
                    return;
                }
                
                // Mark as having listener
                btn.dataset.listenerAttached = 'true';
                
                // Add click listener with proper closure
                btn.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    // Prevent processing if already sending
                    if (state.isProcessing) {
                        console.log('⏸️ Already processing, ignoring quick action click');
                        return;
                    }
                    
                    const message = this.getAttribute('data-message');
                    if (message) {
                        console.log(`🎯 Quick action clicked: "${message}"`);
                        handleQuickAction(message);
                    } else {
                        console.warn('⚠️ Quick action button has no data-message attribute');
                    }
                }, { once: false }); // Allow multiple clicks, but controlled by state.isProcessing
                
                console.log(`✅ Attached listener to button ${index}: "${btn.textContent.trim()}"`);
            });
        }

        console.log('✅ All event listeners attached');
    }

    /**
     * Toggle chatbot open/close
     */
    function toggleChatbot() {
        console.log('🔄 Toggling chatbot, current state:', state.isOpen);
        
        state.isOpen = !state.isOpen;
        
        if (state.isOpen) {
            console.log('📖 Opening chatbot...');
            elements.chatbotContainer.classList.add('active');
            elements.chatbotToggle.classList.add('active');
            elements.chatIcon.style.display = 'none';
            elements.closeIcon.style.display = 'block';
            
            // Focus input
            setTimeout(() => {
                if (elements.chatbotInput) {
                    elements.chatbotInput.focus();
                }
            }, 300);
            
            console.log('✅ Chatbot opened');
        } else {
            console.log('📕 Closing chatbot...');
            elements.chatbotContainer.classList.remove('active');
            elements.chatbotToggle.classList.remove('active');
            elements.chatIcon.style.display = 'block';
            elements.closeIcon.style.display = 'none';
            
            console.log('✅ Chatbot closed');
        }
    }

    /**
     * Auto-resize textarea based on content
     */
    function autoResizeTextarea() {
        const textarea = elements.chatbotInput;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 100) + 'px';
    }

    /**
     * Handle input keydown events
     */
    function handleInputKeydown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    }

    /**
     * Handle quick action button clicks - FIXED
     * @param {string} message - The message to send
     */
    function handleQuickAction(message) {
        if (!message) {
            console.warn('⚠️ handleQuickAction called with empty message');
            return;
        }
        
        if (state.isProcessing) {
            console.log('⏸️ Already processing, cannot handle quick action');
            return;
        }
        
        console.log('📝 Handling quick action:', message);
        
        // Set the input value
        elements.chatbotInput.value = message;
        
        // Send the message
        sendMessage();
    }

    /**
     * Add message to chat
     */
    function addMessage(content, isUser = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user' : 'bot'}`;
        
        const time = new Date().toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        
        messageDiv.innerHTML = `
            <div class="message-avatar">${isUser ? 'You' : 'NS'}</div>
            <div class="message-content">
                <div class="message-bubble">${escapeHtml(content)}</div>
                <div class="message-time">${time}</div>
            </div>
        `;
        
        // Insert before typing indicator
        const typingMessage = elements.typingIndicator.closest('.message');
        elements.chatbotMessages.insertBefore(messageDiv, typingMessage);
        
        // Store in history
        state.messageHistory.push({
            content,
            isUser,
            timestamp: new Date(),
        });
        
        // Scroll to bottom
        scrollToBottom();
    }

    /**
     * Show/Hide typing indicator
     */
    function setTyping(isTyping) {
        if (isTyping) {
            elements.typingIndicator.classList.add('active');
        } else {
            elements.typingIndicator.classList.remove('active');
        }
        scrollToBottom();
    }

    /**
     * Scroll to bottom of messages
     */
    function scrollToBottom() {
        if (elements.chatbotMessages) {
            requestAnimationFrame(() => {
                elements.chatbotMessages.scrollTop = elements.chatbotMessages.scrollHeight;
            });
        }
    }

    /**
     * Escape HTML to prevent XSS
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML.replace(/\n/g, '<br>');
    }

    /**
     * Show error message
     */
    function showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message || 'Sorry, there was an error processing your message. Please try again.';
        
        const typingMessage = elements.typingIndicator.closest('.message');
        elements.chatbotMessages.insertBefore(errorDiv, typingMessage);
        scrollToBottom();
        
        // Auto-remove error after 5 seconds
        setTimeout(() => {
            errorDiv.remove();
        }, 5000);
    }

    /**
     * Send message to backend - FIXED: Proper locking to prevent double-send
     */
    async function sendMessage() {
        const message = elements.chatbotInput.value.trim();
        
        // CRITICAL: Check if already processing FIRST
        if (state.isProcessing) {
            console.log('⏸️ Already processing a message, ignoring this call');
            return;
        }
        
        // Check for empty message
        if (!message) {
            console.log('⏸️ Empty message, not sending');
            return;
        }
        
        console.log('📤 Sending message:', message);
        
        // LOCK: Set processing state IMMEDIATELY
        state.isProcessing = true;
        
        // Add user message to UI
        addMessage(message, true);
        
        // Clear input field immediately
        elements.chatbotInput.value = '';
        elements.chatbotInput.style.height = 'auto';
        
        // Disable send button
        elements.chatbotSend.disabled = true;
        
        // Show typing indicator
        setTyping(true);
        
        try {
            // Send request to backend
            const response = await fetch(CONFIG.apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CONFIG.csrfToken,
                },
                body: JSON.stringify({ 
                    message,
                    history: state.messageHistory.slice(-10),
                }),
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Hide typing indicator
            setTyping(false);
            
            // Add bot response
            if (data.response) {
                addMessage(data.response);
                console.log('✅ Response received and displayed');
            } else if (data.error) {
                showError(data.error);
            } else {
                addMessage('I apologize, but I could not process your request.');
            }
            
        } catch (error) {
            console.error('❌ Error sending message:', error);
            setTyping(false);
            showError();
        } finally {
            // UNLOCK: Re-enable everything
            elements.chatbotSend.disabled = false;
            state.isProcessing = false;
            elements.chatbotInput.focus();
            
            console.log('✅ Message processing complete, ready for next message');
        }
    }

    /**
     * Public API
     */
    window.NormanChatbot = {
        open: function() {
            console.log('🔓 Public API: Opening chatbot');
            if (!state.isOpen) toggleChatbot();
        },
        close: function() {
            console.log('🔒 Public API: Closing chatbot');
            if (state.isOpen) toggleChatbot();
        },
        sendMessage: function(message) {
            if (message && typeof message === 'string' && !state.isProcessing) {
                elements.chatbotInput.value = message;
                sendMessage();
            }
        },
        clearHistory: function() {
            state.messageHistory = [];
            console.log('🗑️ Chat history cleared');
        },
        getHistory: function() {
            return [...state.messageHistory];
        },
        toggle: function() {
            console.log('🔄 Public API: Toggling chatbot');
            toggleChatbot();
        },
        // Debug function
        getState: function() {
            return { ...state };
        }
    };

    // Initialize when script loads
    init();

    console.log('✅ Chatbot initialization complete');

})();