/**
 * NORMAN SLE Chatbot Widget - WITH FEEDBACK + RETRY SYSTEM
 * Features:
 * - Fixed: Double-sending messages from quick action buttons
 * - NEW: Feedback buttons (👍 Helpful / 👎 Try Another Source)
 * - NEW: Multi-tier retry system (FAQ → PDF RAG → SQL Agent)
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
        lastUserMessage: '', // NEW: Track last question for retry
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
        
        // Quick action buttons
        if (elements.quickActionBtns && elements.quickActionBtns.length > 0) {
            console.log(`📌 Attaching ${elements.quickActionBtns.length} quick action listeners`);
            
            elements.quickActionBtns.forEach((btn, index) => {
                if (btn.dataset.listenerAttached === 'true') {
                    console.log(`⏭️ Button ${index} already has listener, skipping`);
                    return;
                }
                
                btn.dataset.listenerAttached = 'true';
                
                btn.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    
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
                }, { once: false });
                
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
     * Handle quick action button clicks
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
        elements.chatbotInput.value = message;
        sendMessage();
    }
    
    /**
     * Add message to chat - NEW: With feedback buttons
     */
    function addMessage(content, isUser = false, metadata = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user' : 'bot'}`;
        
        const time = new Date().toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        const messageBubble = document.createElement('div');
        messageBubble.className = 'message-bubble';
        messageBubble.innerHTML = escapeHtml(content);
        
        const messageTime = document.createElement('div');
        messageTime.className = 'message-time';
        messageTime.textContent = time;
        
        messageContent.appendChild(messageBubble);
        messageContent.appendChild(messageTime);
        
        const messageAvatar = document.createElement('div');
        messageAvatar.className = 'message-avatar';
        messageAvatar.textContent = isUser ? 'You' : 'NS';
        
        messageDiv.appendChild(messageAvatar);
        messageDiv.appendChild(messageContent);
        
        // NEW: Add feedback buttons for bot messages (if retry is available)
        if (!isUser && metadata && metadata.can_retry) {
            const feedbackDiv = createFeedbackButtons(metadata);
            messageContent.appendChild(feedbackDiv);
        }
        
        // Insert before typing indicator
        const typingMessage = elements.typingIndicator.closest('.message');
        elements.chatbotMessages.insertBefore(messageDiv, typingMessage);
        
        // Store in history
        state.messageHistory.push({
            content,
            isUser,
            timestamp: new Date(),
        });
        
        scrollToBottom();
    }
    
    /**
     * NEW: Create feedback buttons (👍 Helpful / 👎 Try Another Source)
     */
    function createFeedbackButtons(metadata) {
        const feedbackDiv = document.createElement('div');
        feedbackDiv.className = 'feedback-buttons';
        feedbackDiv.style.marginTop = '10px';
        feedbackDiv.style.display = 'flex';
        feedbackDiv.style.gap = '10px';
        feedbackDiv.style.flexWrap = 'wrap';
        
        // Thumbs up button
        const thumbsUpBtn = document.createElement('button');
        thumbsUpBtn.innerHTML = '👍 Helpful';
        thumbsUpBtn.className = 'feedback-btn';
        thumbsUpBtn.style.cssText = `
            padding: 6px 12px;
            border: 1px solid #4CAF50;
            border-radius: 4px;
            background: white;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s;
        `;
        thumbsUpBtn.onmouseover = () => thumbsUpBtn.style.background = '#f1f8f4';
        thumbsUpBtn.onmouseout = () => thumbsUpBtn.style.background = 'white';
        thumbsUpBtn.onclick = () => handleFeedback(true, metadata, feedbackDiv);
        
        // Thumbs down button (retry)
        const thumbsDownBtn = document.createElement('button');
        thumbsDownBtn.innerHTML = '👎 Try Another Source';
        thumbsDownBtn.className = 'feedback-btn';
        thumbsDownBtn.style.cssText = `
            padding: 6px 12px;
            border: 1px solid #f44336;
            border-radius: 4px;
            background: white;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s;
        `;
        thumbsDownBtn.onmouseover = () => thumbsDownBtn.style.background = '#fef1f0';
        thumbsDownBtn.onmouseout = () => thumbsDownBtn.style.background = 'white';
        thumbsDownBtn.onclick = () => retryWithNextTier(metadata, feedbackDiv);
        
        feedbackDiv.appendChild(thumbsUpBtn);
        feedbackDiv.appendChild(thumbsDownBtn);
        
        return feedbackDiv;
    }
    
    /**
     * NEW: Handle feedback button clicks
     */
    function handleFeedback(isPositive, metadata, feedbackDiv) {
        console.log(`📊 Feedback: ${isPositive ? 'Helpful' : 'Not helpful'}, Tier: ${metadata.tier}`);
        
        // Update UI
        feedbackDiv.innerHTML = isPositive ? 
            '<span style="color: #4CAF50; font-size: 13px;">✓ Thank you for your feedback!</span>' : 
            '<span style="color: #f44336; font-size: 13px;">✓ Feedback recorded</span>';
        
        // Optional: Send feedback to backend for analytics
        // (You can implement this later)
    }
    
    /**
     * NEW: Retry with next tier
     */
    function retryWithNextTier(metadata, feedbackDiv) {
        if (state.isProcessing) {
            console.log('⏸️ Already processing, cannot retry');
            return;
        }
        
        console.log(`🔄 Retrying with next tier (skipping tier ${metadata.tier})`);
        
        // Update UI
        feedbackDiv.innerHTML = '<span style="color: #2196F3; font-size: 13px;">🔄 Searching another source...</span>';
        
        // Send retry request with skip_tier
        if (state.lastUserMessage) {
            sendMessage(state.lastUserMessage, metadata.tier);
        } else {
            console.error('❌ No last user message to retry');
        }
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
     * Get CSRF token from cookie
     */
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    
    /**
     * Send message to backend - NEW: With skip_tier support
     * @param {string} message - Message to send (optional, uses input if not provided)
     * @param {number} skipTier - Which tier to skip (0 = none, 1 = skip FAQ, 2 = skip FAQ+RAG)
     */
    async function sendMessage(message = null, skipTier = 0) {
        const text = message || elements.chatbotInput.value.trim();
        
        // CRITICAL: Check if already processing FIRST
        if (state.isProcessing) {
            console.log('⏸️ Already processing a message, ignoring this call');
            return;
        }
        
        // Check for empty message
        if (!text) {
            console.log('⏸️ Empty message, not sending');
            return;
        }
        
        console.log(`📤 Sending message: "${text}" (skip_tier=${skipTier})`);
        
        // LOCK: Set processing state IMMEDIATELY
        state.isProcessing = true;
        
        // Store last user message for retry
        if (!message) {
            state.lastUserMessage = text;
        }
        
        // Add user message to UI (only if it's a new message, not a retry)
        if (!message) {
            addMessage(text, true);
        }
        
        // Clear input field immediately (only if it's a new message)
        if (!message) {
            elements.chatbotInput.value = '';
            elements.chatbotInput.style.height = 'auto';
        }
        
        // Disable send button
        elements.chatbotSend.disabled = true;
        
        // Show typing indicator
        setTyping(true);
        
        try {
            // Get CSRF token
            const csrfToken = getCookie('csrftoken') || CONFIG.csrfToken;
            
            // Send request to backend
            const response = await fetch(CONFIG.apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify({ 
                    message: text,
                    skip_tier: skipTier,  // NEW: Tell backend which tier to skip
                    history: state.messageHistory.slice(-10),
                }),
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Hide typing indicator
            setTyping(false);
            
            // Add bot response with metadata
            if (data.response) {
                addMessage(data.response, false, data);
                console.log(`✅ Response received from Tier ${data.tier || '?'}`);
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
        getState: function() {
            return { ...state };
        }
    };
    
    // Initialize when script loads
    init();
    console.log('✅ Chatbot initialization complete with feedback system');
})();