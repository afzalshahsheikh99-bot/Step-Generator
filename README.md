# AI Agent - Notes Step Generator

An intelligent web application that uses Google's Gemini AI to automatically generate step-by-step instructions from images within a notes.zip file structure.

## Features

- 🚀 **AI-Powered Generation**: Uses Google Gemini 3 Pro to analyze images and generate detailed steps
- 📁 **Smart Structure Parsing**: Automatically parses the notes.zip file structure with parent and child nodes
- 🎨 **Beautiful UI/UX**: Modern, responsive interface with smooth animations
- 🖼️ **Image Preview**: Preview images before generating steps
- 📝 **Auto-Save**: Generated steps are automatically saved to description.txt files
- ⬇️ **Export**: Download the updated notes.zip file with all generated steps

## File Structure

The application expects the following structure in notes.zip:

```
notes.zip
├── Findings#auth/           (Parent node)
│   └── information.txt       (Finding description)
│   └── Findings#auth-1/      (Child node)
│       ├── 1/               (Step node)
│       │   ├── [images]/     (Screenshots for this step)
│       │   └── description.txt  (Generated steps)
│       ├── 2/
│       │   ├── [images]/
│       │   └── description.txt
│       └── ...
└── ...
```

## Installation

1. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application**:
   ```bash
   python app.py
   ```

3. **Open your browser**:
   Navigate to `http://localhost:5000`

## Usage

1. **Upload notes.zip**: Drag and drop or click to upload your notes.zip file
2. **Browse Structure**: Explore the findings and child nodes
3. **View Images**: Click "View Images" to preview screenshots for each step
4. **Generate Steps**: Click "Generate AI Steps" to let AI analyze images and create step-by-step instructions
5. **Download**: Click "Download Updated ZIP" to get the updated notes.zip with all generated steps

## API Key

The application uses Google Gemini AI. The API key is configured in `app.py`:
```python
genai.configure(api_key="AIzaSyAb8qYXZWwE8LIX5CFM5geQ0k0FBIt5mCw")
```

To use your own API key:
1. Get an API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Replace the API key in `app.py` with your own

## Example Output

The AI generates steps in the following format:

```
1) Login with the maker "Virat_maker1", navigate to "Transfers" and click on the "Initiate Transfer". Click on the "Single Transfer".

2) Now, select the "Debit Account" and the "Credit Account".

3) Observe the request and response. Note the parameter "Accountno" : "1001641537".

4) Now change the value of parameter "Accountno" to "1000062974".

5) Observe the response.
```

## Tech Stack

- **Backend**: Flask (Python)
- **AI Model**: Google Gemini 3 Pro
- **Frontend**: HTML5, CSS3, JavaScript (vanilla)
- **Image Processing**: Pillow (PIL)

## Development

The application is structured as follows:

- `app.py`: Main Flask application with API endpoints
- `templates/index.html`: Frontend interface
- `requirements.txt`: Python dependencies
- `uploads/`: Temporary storage for uploaded files (auto-generated)

## Features Breakdown

### Upload & Extraction
- Accepts .zip files up to 16MB
- Automatically extracts and parses the file structure
- Validates file format before processing

### AI Generation
- Analyzes multiple images per node
- Uses finding description as context
- Generates chained, sequential steps
- Handles errors gracefully

### User Interface
- Expandable/collapsible tree structure
- Real-time status indicators
- Loading animations
- Modal image preview
- Success/error notifications
- Responsive design for all screen sizes

## Troubleshooting

**Issue**: "Upload failed" error
- **Solution**: Ensure the file is a valid .zip archive

**Issue**: "No images found" error
- **Solution**: Check that the node folders contain image files (.jpg, .png, .jpeg, .gif, .bmp, .webp)

**Issue**: AI generation errors
- **Solution**: Check your API key is valid and you have sufficient quota

## License

This project is provided as-is for educational and commercial use.
