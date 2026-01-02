// DOM Elements
const uploadSection = document.getElementById('upload-section');
const uploadContainer = document.getElementById('upload-container');
const uploadArea = document.getElementById('upload-area');
const fileInput = document.getElementById('file-input');
const fileInfo = document.getElementById('file-info');
const fileName = document.getElementById('file-name');
const fileSize = document.getElementById('file-size');
const fileRemove = document.getElementById('file-remove');
const actionButtons = document.getElementById('action-buttons');
const processBtn = document.getElementById('process-btn');
const processingSection = document.getElementById('processing-section');
const findingsCount = document.getElementById('findings-count');
const stepsCount = document.getElementById('steps-count');
const imagesCount = document.getElementById('images-count');
const processingStatusText = document.getElementById('processing-status-text');
const logsContainer = document.getElementById('logs-container');
const logsList = document.getElementById('logs-list');
const logsToggle = document.getElementById('logs-toggle');
const resultsSection = document.getElementById('results-section');
const resultFindings = document.getElementById('result-findings');
const resultSteps = document.getElementById('result-steps');
const resultImages = document.getElementById('result-images');
const downloadBtn = document.getElementById('download-btn');
const resetBtn = document.getElementById('reset-btn');
const errorSection = document.getElementById('error-section');
const errorMessage = document.getElementById('error-message');
const errorResetBtn = document.getElementById('error-reset-btn');

// State
let uploadedFile = null;
let statusCheckInterval = null;
let isProcessing = false;

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function initializeApp() {
    setupUploadHandlers();
    setupButtonHandlers();
    setupLogsToggle();
}

// Upload Handlers
function setupUploadHandlers() {
    // Click to upload
    uploadArea.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    // Drag and drop
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        if (e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            if (file.name.endsWith('.zip')) {
                handleFileUpload(file);
            } else {
                showNotification('Please upload a ZIP file', 'error');
            }
        }
    });

    // Remove file
    fileRemove.addEventListener('click', (e) => {
        e.stopPropagation();
        removeFile();
    });
}

function handleFileUpload(file) {
    if (!file.name.endsWith('.zip')) {
        showNotification('Please upload a ZIP file', 'error');
        return;
    }

    if (file.size > 100 * 1024 * 1024) { // 100MB
        showNotification('File size exceeds 100MB limit', 'error');
        return;
    }

    uploadedFile = file;
    
    // Update UI
    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);
    
    uploadArea.style.display = 'none';
    fileInfo.style.display = 'block';
    actionButtons.style.display = 'flex';
    
    // Upload to server
    uploadFileToServer(file);
}

function uploadFileToServer(file) {
    const formData = new FormData();
    formData.append('file', file);

    // Show loading state
    processBtn.disabled = true;
    processBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>Uploading...</span>';

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            processBtn.disabled = false;
            processBtn.innerHTML = '<i class="fas fa-magic"></i> <span>Process with AI</span>';
            showNotification('File uploaded successfully', 'success');
        } else {
            throw new Error(data.error || 'Upload failed');
        }
    })
    .catch(error => {
        console.error('Upload error:', error);
        processBtn.disabled = false;
        processBtn.innerHTML = '<i class="fas fa-magic"></i> <span>Process with AI</span>';
        showNotification('Upload failed: ' + error.message, 'error');
        removeFile();
    });
}

function removeFile() {
    uploadedFile = null;
    fileInput.value = '';
    
    // Reset UI
    uploadArea.style.display = 'block';
    fileInfo.style.display = 'none';
    actionButtons.style.display = 'none';
    
    // Reset other sections
    processingSection.style.display = 'none';
    resultsSection.style.display = 'none';
    errorSection.style.display = 'none';
    
    // Clear logs
    logsList.innerHTML = `
        <div class="log-entry">
            <span class="log-time">--:--:--</span>
            <span class="log-message">Waiting to start...</span>
        </div>
    `;
    
    // Reset counters
    findingsCount.textContent = '0';
    stepsCount.textContent = '0';
    imagesCount.textContent = '0';
}

// Button Handlers
function setupButtonHandlers() {
    // Process button
    processBtn.addEventListener('click', () => {
        startProcessing();
    });

    // Download button
    downloadBtn.addEventListener('click', () => {
        window.location.href = '/download';
    });

    // Reset buttons
    resetBtn.addEventListener('click', () => {
        resetApp();
    });

    errorResetBtn.addEventListener('click', () => {
        resetApp();
    });
}

function startProcessing() {
    isProcessing = true;
    
    // Update UI
    uploadSection.style.display = 'none';
    processingSection.style.display = 'block';
    
    // Clear logs
    logsList.innerHTML = '';
    
    // Start processing
    processBtn.disabled = true;
    processBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>Processing...</span>';

    fetch('/process', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Keep checking status until complete
            startStatusCheck();
        } else {
            throw new Error(data.error || 'Processing failed');
        }
    })
    .catch(error => {
        console.error('Processing error:', error);
        showError(error.message);
        isProcessing = false;
    });
}

function startStatusCheck() {
    statusCheckInterval = setInterval(checkStatus, 1000);
}

function checkStatus() {
    fetch('/status')
        .then(response => response.json())
        .then(data => {
            // Update counters
            findingsCount.textContent = data.findings || 0;
            stepsCount.textContent = data.steps || 0;
            imagesCount.textContent = data.images || 0;
            
            // Update logs
            if (data.logs && data.logs.length > 0) {
                updateLogs(data.logs);
            }
            
            // Update status text
            if (data.complete) {
                processingStatusText.textContent = 'Processing complete!';
                clearInterval(statusCheckInterval);
                showResults(data);
            } else if (data.images > 0) {
                processingStatusText.textContent = `Processing images (${data.images} analyzed)`;
            } else if (data.steps > 0) {
                processingStatusText.textContent = `Analyzing steps (${data.steps} processed)`;
            } else if (data.findings > 0) {
                processingStatusText.textContent = `Processing findings (${data.findings} analyzed)`;
            }
        })
        .catch(error => {
            console.error('Status check error:', error);
        });
}

function updateLogs(logs) {
    // Get current log entries
    const currentLogMessages = Array.from(logsList.querySelectorAll('.log-message')).map(el => el.textContent);
    
    // Add new logs
    logs.forEach(log => {
        if (!currentLogMessages.includes(log.message)) {
            addLogEntry(log);
        }
    });
    
    // Scroll to bottom
    logsContainer.scrollTop = logsContainer.scrollHeight;
}

function addLogEntry(log) {
    const logEntry = document.createElement('div');
    logEntry.className = 'log-entry';
    
    const logTime = document.createElement('span');
    logTime.className = 'log-time';
    logTime.textContent = log.timestamp;
    
    const logMessage = document.createElement('span');
    logMessage.className = 'log-message';
    logMessage.textContent = log.message;
    
    if (log.level) {
        logMessage.classList.add(log.level);
    }
    
    logEntry.appendChild(logTime);
    logEntry.appendChild(logMessage);
    logsList.appendChild(logEntry);
}

function showResults(data) {
    isProcessing = false;
    
    // Update results
    if (data.stats) {
        resultFindings.textContent = data.stats.findings || 0;
        resultSteps.textContent = data.stats.steps || 0;
        resultImages.textContent = data.stats.images || 0;
    }
    
    // Show results section
    processingSection.style.display = 'none';
    resultsSection.style.display = 'block';
    
    showNotification('Processing completed successfully!', 'success');
}

function showError(message) {
    processingSection.style.display = 'none';
    errorSection.style.display = 'block';
    errorMessage.textContent = message;
    
    showNotification('Processing failed: ' + message, 'error');
}

function resetApp() {
    // Stop status checking
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
        statusCheckInterval = null;
    }
    
    // Call reset endpoint
    fetch('/reset', {
        method: 'POST'
    })
    .then(() => {
        // Reset UI
        isProcessing = false;
        uploadedFile = null;
        
        uploadSection.style.display = 'block';
        processingSection.style.display = 'none';
        resultsSection.style.display = 'none';
        errorSection.style.display = 'none';
        
        removeFile();
    })
    .catch(error => {
        console.error('Reset error:', error);
        // Force reset UI anyway
        uploadSection.style.display = 'block';
        processingSection.style.display = 'none';
        resultsSection.style.display = 'none';
        errorSection.style.display = 'none';
        removeFile();
    });
}

// Logs Toggle
function setupLogsToggle() {
    logsToggle.addEventListener('click', () => {
        logsContainer.classList.toggle('collapsed');
        logsToggle.classList.toggle('collapsed');
    });
}

// Utility Functions
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        border-radius: 0.5rem;
        color: white;
        font-weight: 500;
        z-index: 10000;
        animation: slideIn 0.3s ease;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    `;
    
    // Set color based on type
    const colors = {
        success: '#059669',
        error: '#EF4444',
        warning: '#F59E0B',
        info: '#2563EB'
    };
    
    notification.style.background = colors[type] || colors.info;
    notification.innerHTML = `
        <div style="display: flex; align-items: center; gap: 0.5rem;">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 3000);
}

// Add fadeOut animation
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeOut {
        from {
            opacity: 1;
            transform: translateX(0);
        }
        to {
            opacity: 0;
            transform: translateX(100px);
        }
    }
`;
document.head.appendChild(style);
