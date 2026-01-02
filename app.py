import google.generativeai as genai
from PIL import Image
import os
import io
import base64
import zipfile
import shutil
import glob
import re
import tempfile
import time
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, send_file, after_this_request
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

# List of API keys
API_KEYS = [
    'AIzaSyDlrfOJuTZP_V1-70GMcEo9vtWdpRFFmjY',
    'AIzaSyDMvynC96au-ztynqSCGu5XGHO2JS-i10I',
    'AIzaSyDltA-iPM00e1C3dWOVRcWwjcvXR2mmp7w',
    'AIzaSyCbS4t9oOjvqAyAoCa5oEmlbdd9_2jv0yE',
    'AIzaSyDq6y5ZhxRX76w_XFgTPuG8wuc35gHP_74'
]

# Model name for Gemini
MODEL_NAME = 'gemini-2.5-flash'


def get_or_create_session_id():
    """Return a stable per-browser session identifier.

    Flask's default SecureCookieSession does not expose a .sid attribute, so we
    generate our own and store it in the signed session cookie.
    """
    session_id = session.get('sid')
    if not session_id:
        session_id = uuid.uuid4().hex
        session['sid'] = session_id
        session.modified = True
    return session_id


def get_next_api_key():
    """Get the next API key in the rotation and configure Gemini with it."""
    current_key_index = session.get('current_api_key_index', 0)
    current_key = API_KEYS[current_key_index]
    
    # Move to the next key for the next request
    session['current_api_key_index'] = (current_key_index + 1) % len(API_KEYS)
    
    # Track API key usage
    if 'api_key_usage_count' not in session:
        session['api_key_usage_count'] = {}
    session['api_key_usage_count'][current_key] = session['api_key_usage_count'].get(current_key, 0) + 1
    
    # Configure Gemini with the current key
    genai.configure(api_key=current_key)
    
    return current_key


def add_log(message, level='info'):
    """Add a log message with timestamp"""
    if 'processing_log' not in session:
        session['processing_log'] = []
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    session['processing_log'].append({
        'timestamp': timestamp,
        'message': message,
        'level': level
    })
    session.modified = True


def remove_step_numbering(text):
    """Remove step numbering (like '1. ') from the beginning of text."""
    pattern = r'^(\d+\.|\[?\d+\]\.?|Step\s+\d+[:\.]\s+)\s*'
    return re.sub(pattern, '', text.strip())


def read_finding_information(finding_dir):
    """Read the information.txt file from the parent finding directory."""
    info_file = os.path.join(finding_dir, "information.txt")
    
    if os.path.exists(info_file):
        try:
            with open(info_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            add_log(f"Successfully read information.txt from {os.path.basename(finding_dir)}")
            return content
        except Exception as e:
            add_log(f"Error reading information.txt from {os.path.basename(finding_dir)}: {str(e)}", "warning")
            return None
    else:
        add_log(f"No information.txt found in {os.path.basename(finding_dir)}", "warning")
        return None


def process_images_with_gemini(images, finding_context=None):
    """Process multiple images with Gemini API and return a consolidated step."""
    try:
        if len(images) == 1:
            return process_single_image_with_gemini(images[0], finding_context)
        
        current_api_key = get_next_api_key()
        model = genai.GenerativeModel(MODEL_NAME)
        
        # Prepare images for the API
        image_parts = []
        for image in images:
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format=image.format if image.format else 'JPEG')
            img_bytes = img_byte_arr.getvalue()
            
            image_parts.append({
                "mime_type": f"image/{image.format.lower() if image.format else 'jpeg'}", 
                "data": base64.b64encode(img_bytes).decode('utf-8')
            })
        
        # Enhanced prompt for more specific image analysis
        context_section = ""
        if finding_context:
            context_section = f"""
**FINDING CONTEXT:**
{finding_context}

**CRITICAL:** Your step must be directly related to this specific security vulnerability. Use the context to understand what is being tested.

"""
        
        prompt = f"""
{context_section}You are a security testing expert analyzing screenshots from a penetration test or security assessment.

**TASK:**
Analyze ALL provided screenshots and generate ONE precise, actionable test step.

**ANALYSIS REQUIREMENTS:**
1. **Identify the specific action** shown in each screenshot
2. **Note all visual indicators:**
   - Red boxes, arrows, or highlights pointing to specific elements
   - Form fields, buttons, links, or inputs being manipulated
   - HTTP requests/responses with parameters, headers, or body content
   - Authentication tokens, cookies, or session identifiers
   - Error messages, success messages, or validation responses
3. **Determine the sequence** of actions if multiple steps are shown
4. **Extract concrete values** (e.g., specific parameter names, values, URLs)

**STEP GENERATION RULES:**
- Generate exactly ONE clear, specific step
- Use present tense, imperative mood (e.g., "Submit the form", "Modify the parameter")
- Include specific element names in quotes: "username" field, "submit" button
- Reference exact parameter names, values, or headers when visible
- Connect multiple actions with "and" or "then" when appropriate
- Maximum 2 sentences, but prefer 1 sentence when possible
- Focus on WHAT is being done, not WHY

**QUALITY EXAMPLES:**
✓ "Submit the login form with username 'admin' and password 'admin123'"
✓ "Change the 'user_id' parameter value to '1' and send the request"
✓ "Intercept the POST request and modify the 'role' parameter to 'administrator'"
✓ "Navigate to the '/admin' endpoint and observe the 403 Forbidden response"
✓ "Copy the 'session_token' from the response headers for the next request"

✗ "This shows how to test for SQL injection by modifying the input" (Too vague)
✗ "Step 1: Login. Step 2: Go to profile." (Split into multiple steps)
✗ "The user is trying to bypass authentication by manipulating cookies" (Descriptive, not actionable)

**SECURITY CONTEXT:**
- This is for a security assessment report
- Steps should be reproducible by another tester
- Precision matters - avoid ambiguous language
- Focus on the technical action, not the business logic

**OUTPUT:**
Return ONLY the step description. No explanations, no numbering, no additional text.
"""
        
        response_parts = [prompt]
        response_parts.extend(image_parts)
        
        response = model.generate_content(response_parts)
        
        # Update processed images count
        if 'processed_images' not in session:
            session['processed_images'] = 0
        session['processed_images'] += len(images)
        session.modified = True
        
        cleaned_response = remove_step_numbering(response.text)
        return cleaned_response
        
    except Exception as e:
        add_log(f"Error processing images: {str(e)}", "error")
        return f"Error processing images: {str(e)}"


def process_single_image_with_gemini(image, finding_context=None):
    """Process a single image with Gemini API and return steps."""
    try:
        current_api_key = get_next_api_key()
        
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format=image.format if image.format else 'JPEG')
        img_bytes = img_byte_arr.getvalue()
        
        model = genai.GenerativeModel(MODEL_NAME)
        
        # Enhanced prompt for single image analysis
        context_section = ""
        if finding_context:
            context_section = f"""
**FINDING CONTEXT:**
{finding_context}

**CRITICAL:** Your step must be directly related to this specific security vulnerability. Use the context to understand what is being tested.

"""
        
        prompt = f"""
{context_section}You are a security testing expert analyzing a single screenshot from a penetration test.

**TASK:**
Examine the screenshot and generate ONE precise, actionable test step.

**VISUAL ANALYSIS:**
1. **Look for highlighted elements:**
   - Red boxes, circles, or arrows indicating focus areas
   - Bolded or underlined text
   - Color-coded sections (often red for vulnerabilities, green for success)
2. **Identify the security-relevant elements:**
   - Input forms with field names and values
   - URL parameters and query strings
   - HTTP headers (Authorization, Cookie, Content-Type, etc.)
   - Request/response body content
   - Buttons, links, or action elements
   - Error messages or validation responses
3. **Extract specific details:**
   - Exact field names (e.g., "username", "email", "api_key")
   - Parameter values being tested (e.g., "1 OR 1=1", "<script>alert(1)</script>")
   - Endpoints or URLs
   - Status codes or response indicators

**STEP GENERATION RULES:**
- Generate exactly ONE clear, specific step
- Use present tense, imperative mood
- Include specific element names in quotes when visible
- Reference exact values, parameters, or endpoints shown
- Maximum 2 sentences (prefer 1)
- Focus on the visible action

**QUALITY EXAMPLES:**
✓ "Submit the login form with username 'admin' and password 'admin123'"
✓ "Intercept the request and modify the 'Authorization' header to 'Bearer invalid_token'"
✓ "Enter '<script>alert(document.cookie)</script>' in the 'search' input field"
✓ "Click the 'Delete' button to remove user ID '5' from the database"
✓ "Observe the 200 OK response with user data for ID '1'"

✗ "This image shows a login form" (Too vague)
✗ "Login as admin and then go to settings" (Multiple steps)
✗ "The attacker is trying to do SQL injection" (Descriptive, not actionable)

**OUTPUT:**
Return ONLY the step description. No numbering, no explanations.
"""
        
        response = model.generate_content([
            prompt,
            {"mime_type": f"image/{image.format.lower() if image.format else 'jpeg'}", 
             "data": base64.b64encode(img_bytes).decode('utf-8')}
        ])
        
        # Update processed images count
        if 'processed_images' not in session:
            session['processed_images'] = 0
        session['processed_images'] += 1
        session.modified = True
        
        cleaned_response = remove_step_numbering(response.text)
        return cleaned_response
        
    except Exception as e:
        add_log(f"Error processing image: {str(e)}", "error")
        return f"Error processing image: {str(e)}"


def find_image_files(directory):
    """Find all image files in a directory."""
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']
    image_files = []
    
    for ext in image_extensions:
        image_files.extend(glob.glob(os.path.join(directory, '*' + ext)))
    
    return image_files


def process_notes_zip(zip_path):
    """Process the notes.zip file according to the specified structure."""
    # Reset counters
    session['processed_findings'] = 0
    session['processed_steps'] = 0
    session['processed_images'] = 0
    session['api_key_usage_count'] = {}
    session['processing_log'] = []
    session.modified = True
    
    temp_dir = tempfile.mkdtemp(prefix="temp_extracted_notes_")
    output_file = None
    
    try:
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        
        add_log(f"Extracting zip file...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        add_log("Processing files...")
        process_findings(extract_dir)
        
        add_log("Repacking the zip file...")
        output_file = os.path.join(temp_dir, "processed_notes.zip")
        repack_zip(extract_dir, output_file)
        
        add_log("Processing complete!", "success")
        session['output_file_path'] = output_file
        session['processing_complete'] = True
        session.modified = True
        
        return output_file
        
    except Exception as e:
        add_log(f"Error processing the zip file: {str(e)}", "error")
        return None


def process_special_folder(special_folder, finding_name, finding_context=None):
    """Process special folders ending with -1, -2, etc."""
    add_log(f"Processing special folder: {os.path.basename(special_folder)} in finding {finding_name}")
    
    folder_1_path = os.path.join(special_folder, "1")
    if os.path.exists(folder_1_path) and os.path.isdir(folder_1_path):
        inner_folder_1_path = os.path.join(folder_1_path, "1")
        if os.path.exists(inner_folder_1_path) and os.path.isdir(inner_folder_1_path):
            img_files = find_image_files(inner_folder_1_path)
            if img_files:
                add_log(f"Found {len(img_files)} images in special path {os.path.basename(special_folder)}/1/1")
                images = []
                for img_file in img_files:
                    try:
                        image = Image.open(img_file)
                        images.append(image)
                    except Exception as e:
                        add_log(f"Error opening image {img_file}: {str(e)}", "warning")
                
                if images:
                    extracted_step = process_images_with_gemini(images, finding_context)
                    
                    desc_file_special = os.path.join(folder_1_path, "Description.txt")
                    with open(desc_file_special, 'w') as f:
                        f.write(extracted_step)
                    
                    add_log(f"Updated description.txt in special path {os.path.basename(special_folder)}/1")
                    return True
    
    add_log(f"No valid images found in special folder {os.path.basename(special_folder)}", "warning")
    return False


def process_findings(base_dir):
    """Process all findings in the notes directory."""
    finding_dirs = [d for d in glob.glob(os.path.join(base_dir, "*")) if os.path.isdir(d)]
    
    add_log(f"Found {len(finding_dirs)} finding directories")
    
    total_findings = len(finding_dirs)
    
    for i, finding_dir in enumerate(finding_dirs):
        finding_name = os.path.basename(finding_dir)
        add_log(f"Processing finding: {finding_name}")
        
        if 'processed_findings' not in session:
            session['processed_findings'] = 0
        session['processed_findings'] += 1
        session.modified = True
        
        finding_context = read_finding_information(finding_dir)
        if finding_context:
            add_log(f"Using finding context for {finding_name}")
        
        # Find special folders (ending with -1, -2, etc.)
        special_folders = [d for d in glob.glob(os.path.join(finding_dir, "*-*")) 
                         if os.path.isdir(d) and re.match(r'.*-\d+$', os.path.basename(d))]
        
        if special_folders:
            add_log(f"Found {len(special_folders)} special folders in finding {finding_name}")
            for special_folder in special_folders:
                process_special_folder(special_folder, finding_name, finding_context)
        
        # Find step directories
        step_dirs = []
        for root, dirs, files in os.walk(finding_dir):
            for dir_name in dirs:
                if re.match(r'^\d+$', dir_name):
                    step_dirs.append(os.path.join(root, dir_name))
        
        step_dirs.sort(key=lambda x: int(os.path.basename(x)))
        
        for step_dir in step_dirs:
            step_num = os.path.basename(step_dir)
            add_log(f"Processing step {step_num}")
            
            if 'processed_steps' not in session:
                session['processed_steps'] = 0
            session['processed_steps'] += 1
            session.modified = True
            
            desc_file = os.path.join(step_dir, "Description.txt")
            image_folders = [d for d in glob.glob(os.path.join(step_dir, "*")) 
                            if os.path.isdir(d) and re.match(r'^\d+$', os.path.basename(d))]
            
            if image_folders:
                image_folders.sort(key=lambda x: int(os.path.basename(x)))
                
                all_images = []
                for img_folder in image_folders:
                    img_files = find_image_files(img_folder)
                    for img_file in img_files:
                        try:
                            image = Image.open(img_file)
                            all_images.append(image)
                        except Exception as e:
                            add_log(f"Error opening image {img_file}: {str(e)}", "warning")
                
                if all_images:
                    add_log(f"Processing {len(all_images)} images for step {step_num}")
                    extracted_step = process_images_with_gemini(all_images, finding_context)
                    
                    with open(desc_file, 'w') as f:
                        f.write(extracted_step)
                    
                    add_log(f"Updated description.txt for step {step_num}")
                else:
                    add_log(f"No valid images found in step {step_num}", "warning")
            else:
                add_log(f"No image folders found in step {step_num}", "warning")


def repack_zip(source_dir, output_zip):
    """Repack the processed directory back into a zip file."""
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_dir)
                zipf.write(file_path, arcname)


# Routes
@app.route('/')
def index():
    """Main page."""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    """Handle file upload."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.zip'):
        return jsonify({'error': 'Please upload a ZIP file'}), 400
    
    # Save the uploaded file
    filename = secure_filename(file.filename)

    # If the user uploads a new zip in the same browser session, clean up the old one.
    previous_upload = session.get('uploaded_file')
    if previous_upload and os.path.exists(previous_upload):
        try:
            os.remove(previous_upload)
        except OSError:
            pass

    session_id = get_or_create_session_id()
    upload_token = uuid.uuid4().hex[:8]
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_{upload_token}_{filename}")
    file.save(upload_path)
    
    # Store the path in session
    session['uploaded_file'] = upload_path
    session['file_size'] = len(request.data) if request.data else os.path.getsize(upload_path)
    session['file_name'] = file.filename
    session.modified = True
    
    return jsonify({
        'success': True,
        'filename': file.filename,
        'size': session['file_size']
    })


@app.route('/process', methods=['POST'])
def process():
    """Process the uploaded file."""
    if 'uploaded_file' not in session:
        return jsonify({'error': 'No file uploaded'}), 400
    
    try:
        zip_path = session['uploaded_file']
        output_path = process_notes_zip(zip_path)
        
        if output_path:
            return jsonify({
                'success': True,
                'message': 'Processing complete',
                'stats': {
                    'findings': session.get('processed_findings', 0),
                    'steps': session.get('processed_steps', 0),
                    'images': session.get('processed_images', 0)
                }
            })
        else:
            return jsonify({'error': 'Processing failed'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/status')
def status():
    """Get processing status."""
    return jsonify({
        'complete': session.get('processing_complete', False),
        'findings': session.get('processed_findings', 0),
        'steps': session.get('processed_steps', 0),
        'images': session.get('processed_images', 0),
        'logs': session.get('processing_log', [])[-50:]  # Last 50 logs
    })


@app.route('/download')
def download():
    """Download the processed file."""
    if 'output_file_path' not in session:
        return jsonify({'error': 'No processed file available'}), 400
    
    output_path = session['output_file_path']
    
    @after_this_request
    def remove_file(response):
        try:
            # Clean up temp directory
            temp_dir = os.path.dirname(output_path)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            
            # Remove uploaded file
            if 'uploaded_file' in session and os.path.exists(session['uploaded_file']):
                os.remove(session['uploaded_file'])
        except Exception as e:
            print(f"Error cleaning up: {e}")
        return response
    
    return send_file(output_path, as_attachment=True, download_name='processed_notes.zip')


@app.route('/reset', methods=['POST'])
def reset():
    """Reset the session."""
    session.clear()
    return jsonify({'success': True})


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
