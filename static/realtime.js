/**
 * Socket.IO client for real-time task progress updates.
 * 
 * This module provides a WebSocket-based alternative to polling for progress updates.
 * Falls back to polling if WebSocket connection fails.
 */

class RealtimeClient {
    constructor() {
        this.socket = null;
        this.connected = false;
        this.fallbackToPolling = false;
        this.callbacks = {
            onProgress: null,
            onComplete: null,
            onError: null
        };
    }
    
    /**
     * Initialize Socket.IO connection
     */
    init() {
        return new Promise((resolve, reject) => {
            // Check if Socket.IO client is available
            if (typeof io === 'undefined') {
                console.warn('Socket.IO client not loaded, will use polling fallback');
                this.fallbackToPolling = true;
                resolve(false);
                return;
            }
            
            try {
                // Connect to the same host
                this.socket = io({
                    transports: ['websocket', 'polling'],
                    reconnection: true,
                    reconnectionAttempts: 5,
                    reconnectionDelay: 1000
                });
                
                this.socket.on('connect', () => {
                    console.log('WebSocket connected:', this.socket.id);
                    this.connected = true;
                    resolve(true);
                });
                
                this.socket.on('disconnect', (reason) => {
                    console.log('WebSocket disconnected:', reason);
                    this.connected = false;
                });
                
                this.socket.on('connect_error', (error) => {
                    console.warn('WebSocket connection error:', error);
                    this.fallbackToPolling = true;
                    reject(error);
                });
                
                // Task progress events
                this.socket.on('task_progress', (data) => {
                    console.log('Received task progress:', data);
                    if (this.callbacks.onProgress) {
                        this.callbacks.onProgress(data);
                    }
                });
                
                this.socket.on('task_complete', (data) => {
                    console.log('Received task complete:', data);
                    if (this.callbacks.onComplete) {
                        this.callbacks.onComplete(data);
                    }
                });
                
                this.socket.on('task_error', (data) => {
                    console.log('Received task error:', data);
                    if (this.callbacks.onError) {
                        this.callbacks.onError(data);
                    }
                });
                
                this.socket.on('subscribed', (data) => {
                    console.log('Subscribed to task:', data.task_id);
                });
                
                // Timeout for initial connection
                setTimeout(() => {
                    if (!this.connected) {
                        console.warn('WebSocket connection timeout, using polling fallback');
                        this.fallbackToPolling = true;
                        resolve(false);
                    }
                }, 5000);
                
            } catch (error) {
                console.error('Failed to initialize WebSocket:', error);
                this.fallbackToPolling = true;
                reject(error);
            }
        });
    }
    
    /**
     * Subscribe to updates for a specific task
     */
    subscribeToTask(taskId) {
        if (!this.socket || !this.connected) {
            console.warn('Cannot subscribe: WebSocket not connected');
            return false;
        }
        
        this.socket.emit('subscribe_task', { task_id: taskId });
        return true;
    }
    
    /**
     * Unsubscribe from task updates
     */
    unsubscribeFromTask(taskId) {
        if (!this.socket || !this.connected) {
            return;
        }
        
        this.socket.emit('unsubscribe_task', { task_id: taskId });
    }
    
    /**
     * Set callback for progress updates
     */
    onProgress(callback) {
        this.callbacks.onProgress = callback;
    }
    
    /**
     * Set callback for completion
     */
    onComplete(callback) {
        this.callbacks.onComplete = callback;
    }
    
    /**
     * Set callback for errors
     */
    onError(callback) {
        this.callbacks.onError = callback;
    }
    
    /**
     * Check if should use polling fallback
     */
    shouldUsePollling() {
        return this.fallbackToPolling || !this.connected;
    }
    
    /**
     * Disconnect from server
     */
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
            this.connected = false;
        }
    }
}

// Export singleton instance
window.realtimeClient = new RealtimeClient();
