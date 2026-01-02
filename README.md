# Notes.zip Processor - AI-Powered Security Assessment Tool

An intelligent web application that uses Google's Gemini AI to automatically generate precise, context-aware test steps from security assessment screenshots within a notes.zip file structure.

## Features

- 🧠 **Enhanced AI Analysis**: Uses Google Gemini 2.5 Flash with specialized prompts for security testing context
- 📁 **Smart Structure Parsing**: Automatically parses notes.zip file structure with parent and child findings
- 🎨 **Modern UI/UX**: Beautiful, responsive interface with smooth animations and real-time updates
- 🔍 **Context-Aware Processing**: Reads information.txt files to understand specific security vulnerabilities
- 📊 **Real-Time Progress**: Live tracking of findings, steps, and images being processed
- 🔄 **API Key Rotation**: Automatic rotation between multiple API keys for reliable processing at scale
- 📝 **Auto-Save**: Generated steps are automatically saved to description.txt files
- ⬇️ **Export**: Download updated notes.zip file with all AI-generated steps

## File Structure

The application expects the following structure in notes.zip:

```
notes.zip
├── Findings#auth/           (Parent finding node)
│   ├── information.txt       (Finding description - provides context)
│   ├── Findings#auth-1/      (Child finding node)
│   │   └── 1/               (Step folder)
│   │       ├── 1/            (Image folder)
│   │       │   ├── [images]/ (Security assessment screenshots)
│   │       │   └── ...
│   │       └── Description.txt (AI-generated steps)
│   ├── 1/                   (Direct step folder)
│   │   ├── 1/               (Image folder)
│   │   │   └── [images]/
│   │   └── Description.txt
│   └── 2/
│       ├── 1/
│       └── Description.txt
└── ...
```

## Installation

1. **Create a virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python app.py
   ```

4. **Open your browser**:
   Navigate to `http://localhost:5000`

## Usage

1. **Upload notes.zip**: Drag and drop or click to upload your notes.zip file (max 100MB)
2. **Process with AI**: Click the "Process with AI" button to start processing
3. **Monitor Progress**: Watch real-time progress of findings, steps, and images being analyzed
4. **View Logs**: Expand the processing logs to see detailed information about each step
5. **Download Results**: Once complete, download your processed notes.zip with all AI-generated steps

## AI Analysis Features

### Context-Aware Step Generation

The AI is specifically tuned for security assessment workflows:

- **Reads finding context**: Extracts information from information.txt to understand the vulnerability
- **Analyzes visual indicators**: Identifies red boxes, highlights, and marked elements
- **Extracts specific details**: Captures field names, parameters, values, and endpoints
- **Generates precise steps**: Creates clear, actionable test steps with concrete details

### Step Quality Standards

Generated steps follow these guidelines:

- Use present tense, imperative mood (e.g., "Submit", "Modify", "Observe")
- Include specific element names in quotes (e.g., "username" field)
- Reference exact parameters, values, and headers when visible
- Maximum 1-2 sentences per step
- Focus on technical actions, not explanations

### Example Output

```
Submit the login form with username 'admin' and password 'admin123'

Change the 'user_id' parameter value to '1' and send the request

Intercept the POST request and modify the 'role' parameter to 'administrator'

Navigate to the '/admin' endpoint and observe the 403 Forbidden response
```

## Configuration

### API Keys

The application uses multiple API keys for rotation. Update the `API_KEYS` list in `app.py`:

```python
API_KEYS = [
    'AIzaSyDlrfOJuTZP_V1-70GMcEo9vtWdpRFFmjY',
    'AIzaSyDMvynC96au-ztynqSCGu5XGHO2JS-i10I',
    # Add more keys here
]
```

To get API keys:
1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create API keys
3. Add them to the `API_KEYS` list

### Model Configuration

The model name is configurable:
```python
MODEL_NAME = 'gemini-2.5-flash'
```

Supported models:
- `gemini-2.5-flash` (fast, cost-effective)
- `gemini-2.5-pro` (slower, more accurate)
- `gemini-1.5-pro` (older, stable)

## Tech Stack

- **Backend**: Flask (Python 3.x)
- **AI Model**: Google Gemini 2.5 Flash
- **Frontend**: HTML5, CSS3, vanilla JavaScript
- **Image Processing**: Pillow (PIL)
- **File Processing**: zipfile, tempfile

## API Endpoints

### `POST /upload`
Upload a notes.zip file for processing.

### `POST /process`
Start processing the uploaded file with AI.

### `GET /status`
Get real-time processing status including:
- Processing completion status
- Number of findings, steps, and images processed
- Recent log entries

### `GET /download`
Download the processed notes.zip file.

### `POST /reset`
Reset the session and clear all uploaded data.

## Development

### Project Structure

```
project/
├── app.py                 # Main Flask application
├── requirements.txt        # Python dependencies
├── templates/
│   └── index.html        # Frontend interface
├── static/
│   ├── styles.css        # Application styles
│   └── app.js           # Frontend JavaScript
└── README.md            # This file
```

### Key Features Breakdown

#### Upload & Processing
- Drag-and-drop file upload
- 100MB file size limit
- Automatic extraction and parsing
- Validation of file structure

#### AI Integration
- Multiple API key rotation
- Context-aware prompt engineering
- Error handling and retry logic
- Batch image processing

#### User Interface
- Modern gradient design
- Responsive layout
- Real-time progress tracking
- Animated loading states
- Collapsible log viewer
- Success/error notifications

## Troubleshooting

**Issue**: "Upload failed" error
- **Solution**: Ensure file is a valid .zip archive and under 100MB

**Issue**: "No images found" error
- **Solution**: Check that step folders contain image files (.jpg, .png, .jpeg, .gif, .bmp, .webp, .tiff)

**Issue**: AI generation errors
- **Solution**: Verify API keys are valid and have sufficient quota

**Issue**: Processing takes too long
- **Solution**: Add more API keys to the rotation or switch to a faster model

**Issue**: Steps are too generic
- **Solution**: Ensure information.txt files exist in parent finding directories to provide context

## Performance Tips

1. **Use multiple API keys**: Add 3-5 API keys to the rotation for parallel processing
2. **Optimize image sizes**: Keep images under 5MB for faster processing
3. **Batch processing**: The app automatically processes all findings in a single zip
4. **Monitor quota**: Check your Google AI Studio usage to avoid rate limits

## Security Notes

- API keys are stored server-side and never exposed to the client
- Uploaded files are stored in temporary directories and cleaned up after processing
- Session-based state management prevents cross-user data leakage
- File size limits prevent resource exhaustion attacks

## License

This project is provided as-is for educational and commercial use.

## Changelog

### v2.0.0
- Removed Streamlit dependency
- Built custom Flask-based UI/UX
- Enhanced AI prompts for security testing context
- Added real-time progress tracking
- Implemented API key rotation
- Added modern responsive design
- Improved error handling and logging

### v1.0.0
- Initial Streamlit-based implementation
- Basic AI step generation
- Simple file upload and processing
