/**
 * NORMAN SLE Chatbot - FINAL COMPLETE VERSION
 * ✅ All messages with avatars (NS or U)
 * ✅ Gradient feedback buttons with text
 * ✅ Category navigation
 * ✅ No duplicate code
 */
(function() {
    'use strict';
    
    if (window.NormanChatbotInitialized) return;
    window.NormanChatbotInitialized = true;
    
    const CONFIG = window.CHATBOT_CONFIG || {
        apiEndpoint: '/api/chatbot/message/',
        csrfToken: document.querySelector('[name=csrfmiddlewaretoken]')?.value || '',
    };
    
    let elements = {};
    const state = {
        isOpen: false,
        isProcessing: false,
        lastUserMessage: '',
        conversationContext: [],
        faqDataByCategory: {}
    };
    
    function init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initElements);
        } else {
            initElements();
        }
    }
    
    function initElements() {
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
            categoriesView: document.getElementById('categoriesView'),
            questionsView: document.getElementById('questionsView'),
            backButton: document.getElementById('backButton'),
        };
        
        attachEventListeners();
        loadCategories();
        scrollToBottom();
    }
    
    function attachEventListeners() {
        if (elements.chatbotToggle) {
            elements.chatbotToggle.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                toggleChatbot();
            });
        }
        
        if (elements.chatbotClose) {
            elements.chatbotClose.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                toggleChatbot();
            });
        }
        
        if (elements.chatbotInput) {
            elements.chatbotInput.addEventListener('input', autoResizeTextarea);
            elements.chatbotInput.addEventListener('keydown', handleInputKeydown);
        }
        
        if (elements.chatbotSend) {
            elements.chatbotSend.addEventListener('click', async function(e) {
                e.preventDefault();
                e.stopPropagation();
                await sendMessage();
            });
        }
        
        if (elements.backButton) {
            elements.backButton.addEventListener('click', showCategories);
        }
        
        // Dynamic quick action buttons (from HTML, not categories)
        document.querySelectorAll('.quick-action-btn').forEach(btn => {
            if (!btn.dataset.listenerAttached) {
                btn.dataset.listenerAttached = 'true';
                btn.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    if (!state.isProcessing) {
                        const message = this.getAttribute('data-message');
                        if (message) {
                            handleQuickAction(message);
                        }
                    }
                });
            }
        });
    }
    
    function handleInputKeydown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    }
    
    function handleQuickAction(message) {
        if (!message || state.isProcessing) return;
        elements.chatbotInput.value = message;
        sendMessage();
    }
    
    function toggleChatbot() {
        state.isOpen = !state.isOpen;
        
        if (state.isOpen) {
            elements.chatbotContainer.classList.add('active');
            elements.chatbotToggle.classList.add('active');
            elements.chatIcon.style.display = 'none';
            elements.closeIcon.style.display = 'block';
            setTimeout(() => elements.chatbotInput?.focus(), 300);
        } else {
            elements.chatbotContainer.classList.remove('active');
            elements.chatbotToggle.classList.remove('active');
            elements.chatIcon.style.display = 'block';
            elements.closeIcon.style.display = 'none';
        }
    }
    
    function autoResizeTextarea() {
        const textarea = elements.chatbotInput;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 100) + 'px';
    }
    
    // ========================================
    // CATEGORY MANAGEMENT
    // ========================================
    function loadCategories() {
        fetch(CONFIG.apiEndpoint + '?action=get_categories')
            .then(response => response.json())
            .then(data => {
                if (data.categories) {
                    state.faqDataByCategory = data.faq_data || {};
                    renderCategories(data.categories);
                }
            })
            .catch(error => {
                console.error('Error loading categories:', error);
            });
    }
    
    function renderCategories(categories) {
        if (!elements.categoriesView) return;
        elements.categoriesView.innerHTML = '';
        
        categories.forEach(category => {
            const btn = document.createElement('button');
            btn.className = 'quick-action-btn category-btn';
            btn.innerHTML = `<span class="category-icon">${category.icon || '●'}</span>${category.display_name || category.name}`;
            btn.addEventListener('click', () => showQuestions(category.name));
            elements.categoriesView.appendChild(btn);
        });
    }
    
    function showQuestions(category) {
        elements.categoriesView.style.display = 'none';
        elements.questionsView.style.display = 'flex';
        elements.backButton.style.display = 'flex';
        
        const questions = state.faqDataByCategory[category] || [];
        elements.questionsView.innerHTML = '';
        
        questions.forEach(item => {
            const btn = document.createElement('button');
            btn.className = 'quick-action-btn question-btn';
            btn.textContent = item.q || item.question;
            btn.addEventListener('click', () => {
                handleQuestionClick(item.q || item.question);
            });
            elements.questionsView.appendChild(btn);
        });
    }
    
    function showCategories() {
        elements.categoriesView.style.display = 'flex';
        elements.questionsView.style.display = 'none';
        elements.backButton.style.display = 'none';
    }
    
    function handleQuestionClick(question) {
        // Add user message
        addMessage(question, true);
        
        // Show typing
        setTyping(true);
        
        // Send to backend
        fetch(CONFIG.apiEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CONFIG.csrfToken
            },
            body: JSON.stringify({ message: question })
        })
        .then(response => response.json())
        .then(data => {
            setTyping(false);
            addMessage(data.response, false, data);
            setTimeout(showCategories, 500);
        })
        .catch(error => {
            setTyping(false);
            addMessage('Sorry, I encountered an error. Please try again.', false);
            setTimeout(showCategories, 500);
        });
    }
    
    // ========================================
    // MESSAGE HANDLING - WITH AVATARS (NS/U)
    // ========================================
    function addMessage(content, isUser = false, metadata = null) {
        const messagesContainer = elements.chatbotMessages;
        if (!messagesContainer) return;
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user' : 'bot'}`;
        
        // Avatar
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'message-avatar';
        avatarDiv.textContent = isUser ? 'U' : 'NS';
        
        // Content wrapper
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // Message bubble
        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'message-bubble';
        bubbleDiv.innerHTML = content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>')
            .replace(/• /g, '• ');
        
        // Time
        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
        
        contentDiv.appendChild(bubbleDiv);
        contentDiv.appendChild(timeDiv);
        
        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        
        // Add feedback buttons for bot messages
        if (!isUser && metadata) {
            const feedbackDiv = createFeedbackButtons(metadata);
            contentDiv.appendChild(feedbackDiv);
        }
        
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    // ========================================
    // FEEDBACK BUTTONS - GRADIENT WITH TEXT
    // ========================================
    function createFeedbackButtons(metadata) {
        const feedbackDiv = document.createElement('div');
        feedbackDiv.className = 'feedback-buttons';
        feedbackDiv.style.cssText = `
            margin-top: 12px;
            display: flex;
            gap: 10px;
            align-items: center;
            padding-top: 12px;
            border-top: 1px solid rgba(0,0,0,0.08);
        `;
        
        // THUMBS UP - GREEN GRADIENT
        const thumbsUpBtn = document.createElement('button');
        thumbsUpBtn.innerHTML = '👍';
        thumbsUpBtn.className = 'feedback-btn feedback-positive';
        thumbsUpBtn.style.cssText = `
            padding: 8px 16px;
            border: 1.5px solid #4CAF50;
            border-radius: 6px;
            background: linear-gradient(135deg, #ffffff 0%, #f1f8f4 100%);
            color: #4CAF50;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
            transition: all 0.2s ease;
            box-shadow: 0 2px 4px rgba(76, 175, 80, 0.1);
        `;
        
        thumbsUpBtn.onmouseover = () => {
            thumbsUpBtn.style.background = 'linear-gradient(135deg, #4CAF50 0%, #66BB6A 100%)';
            thumbsUpBtn.style.color = 'white';
            thumbsUpBtn.style.transform = 'translateY(-1px)';
            thumbsUpBtn.style.boxShadow = '0 4px 8px rgba(76, 175, 80, 0.2)';
        };
        
        thumbsUpBtn.onmouseout = () => {
            thumbsUpBtn.style.background = 'linear-gradient(135deg, #ffffff 0%, #f1f8f4 100%)';
            thumbsUpBtn.style.color = '#4CAF50';
            thumbsUpBtn.style.transform = 'translateY(0)';
            thumbsUpBtn.style.boxShadow = '0 2px 4px rgba(76, 175, 80, 0.1)';
        };
        
        thumbsUpBtn.onclick = () => handleFeedback(true, metadata, feedbackDiv);
        
        // THUMBS DOWN
        const thumbsDownBtn = document.createElement('button');
        
        if (metadata.can_retry) {
            // BLUE GRADIENT - Can retry
            thumbsDownBtn.innerHTML = `👎`;
            thumbsDownBtn.className = 'feedback-btn feedback-retry';
            thumbsDownBtn.style.cssText = `
                padding: 8px 16px;
                border: 1.5px solid #2196F3;
                border-radius: 6px;
                background: linear-gradient(135deg, #ffffff 0%, #e3f2fd 100%);
                color: #2196F3;
                cursor: pointer;
                font-size: 13px;
                font-weight: 500;
                transition: all 0.2s ease;
                box-shadow: 0 2px 4px rgba(33, 150, 243, 0.1);
            `;
            
            thumbsDownBtn.onmouseover = () => {
                thumbsDownBtn.style.background = 'linear-gradient(135deg, #2196F3 0%, #42A5F5 100%)';
                thumbsDownBtn.style.color = 'white';
                thumbsDownBtn.style.transform = 'translateY(-1px)';
                thumbsDownBtn.style.boxShadow = '0 4px 8px rgba(33, 150, 243, 0.2)';
            };
            
            thumbsDownBtn.onmouseout = () => {
                thumbsDownBtn.style.background = 'linear-gradient(135deg, #ffffff 0%, #e3f2fd 100%)';
                thumbsDownBtn.style.color = '#2196F3';
                thumbsDownBtn.style.transform = 'translateY(0)';
                thumbsDownBtn.style.boxShadow = '0 2px 4px rgba(33, 150, 243, 0.1)';
            };
        } else {
            // ORANGE GRADIENT - Final tier
            thumbsDownBtn.innerHTML = '👎';
            thumbsDownBtn.className = 'feedback-btn feedback-final';
            thumbsDownBtn.style.cssText = `
                padding: 8px 16px;
                border: 1.5px solid #FF9800;
                border-radius: 6px;
                background: linear-gradient(135deg, #ffffff 0%, #fff3e0 100%);
                color: #FF9800;
                cursor: pointer;
                font-size: 13px;
                font-weight: 500;
                transition: all 0.2s ease;
                box-shadow: 0 2px 4px rgba(255, 152, 0, 0.1);
            `;
            
            thumbsDownBtn.onmouseover = () => {
                thumbsDownBtn.style.background = 'linear-gradient(135deg, #FF9800 0%, #FFB74D 100%)';
                thumbsDownBtn.style.color = 'white';
                thumbsDownBtn.style.transform = 'translateY(-1px)';
                thumbsDownBtn.style.boxShadow = '0 4px 8px rgba(255, 152, 0, 0.2)';
            };
            
            thumbsDownBtn.onmouseout = () => {
                thumbsDownBtn.style.background = 'linear-gradient(135deg, #ffffff 0%, #fff3e0 100%)';
                thumbsDownBtn.style.color = '#FF9800';
                thumbsDownBtn.style.transform = 'translateY(0)';
                thumbsDownBtn.style.boxShadow = '0 2px 4px rgba(255, 152, 0, 0.1)';
            };
        }
        
        thumbsDownBtn.onclick = () => handleFeedback(false, metadata, feedbackDiv);
        
        feedbackDiv.appendChild(thumbsUpBtn);
        feedbackDiv.appendChild(thumbsDownBtn);
        
        return feedbackDiv;
    }
    
    function handleFeedback(isHelpful, metadata, feedbackDiv) {
        // Send feedback to backend
        fetch('/api/chatbot/feedback/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                helpful: isHelpful,
                tier: metadata.tier,
                tier_name: metadata.tier_name,
                type: metadata.type,
                timestamp: new Date().toISOString()
            })
        });
        
        if (isHelpful) {
            feedbackDiv.innerHTML = `
                <div style="
                    color: #4CAF50; 
                    font-size: 13px; 
                    font-weight: 500;
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    padding: 8px 0;
                ">
                    <span style="font-size: 16px;">✓</span>
                    <span>Thank you for your feedback!</span>
                </div>
            `;
        } else {
            if (metadata.can_retry) {
                feedbackDiv.innerHTML = `
                    <div style="
                        color: #2196F3; 
                        font-size: 13px; 
                        font-weight: 500;
                        display: flex;
                        align-items: center;
                        gap: 6px;
                        padding: 8px 0;
                    ">
                        <span style="font-size: 16px;">🔄</span>
                        <span>Searching ${metadata.next_tier}...</span>
                    </div>
                `;
                
                sendMessage(state.lastUserMessage, metadata.tier);
            } else {
                // Tier 4 tip box
                feedbackDiv.innerHTML = `
                    <div style="
                        margin-top: 12px;
                        padding: 16px;
                        background: linear-gradient(135deg, #FFF8E1 0%, #FFECB3 100%);
                        border-left: 4px solid #FF9800;
                        border-radius: 8px;
                        box-shadow: 0 2px 8px rgba(255, 152, 0, 0.1);
                    ">
                        <div style="
                            color: #E65100; 
                            font-size: 14px; 
                            font-weight: 600;
                            display: flex;
                            align-items: center;
                            gap: 8px;
                            margin-bottom: 10px;
                        ">
                            <span style="font-size: 18px;">💡</span>
                            <span>Try asking your question differently</span>
                        </div>
                        <div style="
                            font-size: 13px; 
                            color: #5D4037; 
                            line-height: 1.6;
                        ">
                            <strong>Tips for better results:</strong><br>
                            • <strong>Be more specific:</strong> "What is X?" → "How does X work in Y context?"<br>
                            • <strong>Use different words:</strong> Try synonyms or related terms<br>
                            • <strong>Break it down:</strong> Ask step-by-step for complex questions
                        </div>
                    </div>
                `;
            }
        }
    }
    
    // ========================================
    // SEND MESSAGE
    // ========================================
    async function sendMessage(message = null, skipTier = 0) {
        if (state.isProcessing) return;
        
        const text = message || elements.chatbotInput.value.trim();
        if (!text) return;
        
        if (text.length > 1000) {
            showError('Message too long (max 1000 characters)');
            return;
        }
        
        state.isProcessing = true;
        
        if (!message) {
            state.lastUserMessage = text;
            addMessage(text, true);
            elements.chatbotInput.value = '';
            elements.chatbotInput.style.height = 'auto';
            
            state.conversationContext.push({
                role: 'user',
                content: text,
                timestamp: new Date().toISOString()
            });
        }
        
        elements.chatbotSend.disabled = true;
        setTyping(true);
        
        try {
            const csrfToken = getCookie('csrftoken') || CONFIG.csrfToken;
            
            if (!csrfToken) {
                throw new Error('CSRF token not found');
            }
            
            const response = await fetch(CONFIG.apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify({
                    message: text,
                    skip_tier: skipTier,
                    history: state.conversationContext.slice(-10)
                }),
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }
            
            const data = await response.json();
            setTyping(false);
            
            if (data.response) {
                addMessage(data.response, false, data);
                
                state.conversationContext.push({
                    role: 'assistant',
                    content: data.response,
                    tier: data.tier,
                    tier_name: data.tier_name,
                    timestamp: new Date().toISOString()
                });
                
                if (state.conversationContext.length > 20) {
                    state.conversationContext = state.conversationContext.slice(-20);
                }
            } else if (data.error) {
                showError(data.error);
            }
            
        } catch (error) {
            setTyping(false);
            
            let errorMessage = 'Sorry, something went wrong. Please try again.';
            
            if (error.message.includes('Failed to fetch')) {
                errorMessage = 'Network error. Please check your connection.';
            } else if (error.message.includes('HTTP 500')) {
                errorMessage = 'Server error. Please try again later.';
            } else if (error.message.includes('CSRF')) {
                errorMessage = 'Security error. Please refresh the page.';
            }
            
            showError(errorMessage);
            
        } finally {
            elements.chatbotSend.disabled = false;
            state.isProcessing = false;
            elements.chatbotInput.focus();
        }
    }
    
    // ========================================
    // UTILITIES
    // ========================================
    function setTyping(isTyping) {
        if (isTyping) {
            elements.typingIndicator?.classList.add('active');
        } else {
            elements.typingIndicator?.classList.remove('active');
        }
        scrollToBottom();
    }
    
    function scrollToBottom() {
        if (elements.chatbotMessages) {
            requestAnimationFrame(() => {
                elements.chatbotMessages.scrollTop = elements.chatbotMessages.scrollHeight;
            });
        }
    }
    
    function showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.style.cssText = `
            background: linear-gradient(135deg, #FFEBEE 0%, #FFCDD2 100%);
            border-left: 4px solid #f44336;
            padding: 12px;
            margin: 8px 0;
            border-radius: 4px;
            color: #c62828;
            font-size: 14px;
            font-weight: 500;
            box-shadow: 0 2px 8px rgba(244, 67, 54, 0.1);
        `;
        errorDiv.textContent = message || 'Sorry, there was an error. Please try again.';
        
        elements.chatbotMessages.appendChild(errorDiv);
        scrollToBottom();
        
        setTimeout(() => errorDiv.remove(), 5000);
    }
    
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
    
    // Public API
    window.NormanChatbot = {
        open: function() {
            if (!state.isOpen) toggleChatbot();
        },
        close: function() {
            if (state.isOpen) toggleChatbot();
        },
        sendMessage: function(message) {
            if (message && typeof message === 'string' && !state.isProcessing) {
                elements.chatbotInput.value = message;
                sendMessage();
            }
        },
        toggle: function() {
            toggleChatbot();
        }
    };
    
    init();
})();