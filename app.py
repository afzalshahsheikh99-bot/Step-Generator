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

# Configuration for multiple AI providers with fallback support
AI_PROVIDERS = {
    'gemini': {
        'models': ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-1.5-pro'],
        'api_keys': [
            'AIzaSyDlrfOJuTZP_V1-70GMcEo9vtWdpRFFmjY',
            'AIzaSyDMvynC96au-ztynqSCGu5XGHO2JS-i10I',
            'AIzaSyDltA-iPM00e1C3dWOVRcWwjcvXR2mmp7w',
            'AIzaSyCbS4t9oOjvqAyAoCa5oEmlbdd9_2jv0yE',
            'AIzaSyDq6y5ZhxRX76w_XFgTPuG8wuc35gHP_74'
        ],
        'config_function': lambda key: genai.configure(api_key=key),
        'model_factory': lambda model_name: genai.GenerativeModel(model_name)
    }
}

# Error keywords that indicate rate limiting
RATE_LIMIT_KEYWORDS = [
    'limit exceed',
    'rate limit',
    'quota exceeded',
    '429',
    'resource exhausted',
    'too many requests'
]

# Maximum retry attempts per provider
MAX_RETRIES = 2


def is_rate_limit_error(error_message):
    """Check if an error message indicates rate limiting."""
    error_lower = str(error_message).lower()
    return any(keyword in error_lower for keyword in RATE_LIMIT_KEYWORDS)


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


def get_next_provider_config(provider_name='gemini'):
    """Get the next available provider configuration with API key rotation."""
    provider = AI_PROVIDERS.get(provider_name)
    if not provider:
        raise ValueError(f"Unknown provider: {provider_name}")
    
    current_key_index = session.get(f'{provider_name}_key_index', 0)
    current_model_index = session.get(f'{provider_name}_model_index', 0)
    
    current_key = provider['api_keys'][current_key_index]
    current_model = provider['models'][current_model_index]
    
    # Track key usage for this provider
    usage_key = f'{provider_name}_api_key_usage'
    if usage_key not in session:
        session[usage_key] = {}
    session[usage_key][current_key] = session[usage_key].get(current_key, 0) + 1
    
    # Rotate keys for next request
    session[f'{provider_name}_key_index'] = (current_key_index + 1) % len(provider['api_keys'])
    
    # Rotate models when all keys are exhausted
    if session[f'{provider_name}_key_index'] == 0:
        session[f'{provider_name}_model_index'] = (current_model_index + 1) % len(provider['models'])
    
    return {
        'provider': provider_name,
        'api_key': current_key,
        'model': current_model,
        'config_function': provider['config_function'],
        'model_factory': provider['model_factory']
    }


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
    pattern = r'^(\d+\.\s*|\[?\d+\]\.?\s*|Step\s+\d+[:\.]	{2})'
    cleaned = re.sub(pattern, '', text.strip())
    return cleaned


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


def prepare_image_for_api(image):
    """Convert PIL Image to base64 encoded bytes for API calls."""
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format=image.format if image.format else 'JPEG')
    img_bytes = img_byte_arr.getvalue()
    
    mime_type = f"image/{image.format.lower() if image.format else 'jpeg'}"
    encoded_data = base64.b64encode(img_bytes).decode('utf-8')
    
    return mime_type, encoded_data


def build_enhanced_prompt(finding_context=None, is_single_image=False):
    """Build the enhanced prompt for image analysis."""
    context_section = ""
    if finding_context:
        context_section = f"""
**FINDING CONTEXT:**
{finding_context}

**CRITICAL:** Your step must be directly related to this specific security vulnerability. Use the context to understand what is being tested.

"""
    
    if is_single_image:
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
    else:
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
    
    return prompt


def generate_with_gemini(config, images, finding_context=None, is_single_image=False):
    """Generate content using Gemini API with the given configuration."""
    try:
        # Configure the provider with current key
        config['config_function'](config['api_key'])
        
        # Create model instance
        model = config['model_factory'](config['model'])
        
        # Prepare images
        image_parts = []
        for image in images:
            mime_type, encoded_data = prepare_image_for_api(image)
            image_parts.append({
                "mime_type": mime_type,
                "data": encoded_data
            })
        
        # Build prompt
        prompt = build_enhanced_prompt(finding_context, is_single_image)
        
        # Prepare request parts
        response_parts = [prompt]
        response_parts.extend(image_parts)
        
        # Generate response
        response = model.generate_content(response_parts)
        
        return response.text
        
    except Exception as e:
        error_msg = str(e)
        add_log(f"Error with {config['model']} using key {config['api_key'][:10]}...: {error_msg}", "warning")
        
        if is_rate_limit_error(error_msg):
            raise RuntimeError(f"Rate limit exceeded: {error_msg}")
        raise


def process_images_with_fallback(images, finding_context=None):
    """Process images with automatic fallback between providers, models, and keys."""
    if len(images) == 1:
        return process_single_image_with_fallback(images[0], finding_context)
    
    # Initialize provider trackers if not exist
    if 'provider_usage' not in session:
        session['provider_usage'] = {'gemini': 0}
    
    # Try each provider
    best_error = None
    last_config = None
    
    for provider_name in AI_PROVIDERS.keys():
        session['provider_usage'][provider_name] = session['provider_usage'].get(provider_name, 0) + 1
        
        # Try multiple attempts within each provider (key/model rotation)
        for attempt in range(MAX_RETRIES * 2):  # Allow more attempts for rotation
            try:
                config = get_next_provider_config(provider_name)
                
                add_log(f"Attempting {config['provider']}::{config['model']} with key {config['api_key'][:10]}... (attempt {attempt+1})")
                
                result = generate_with_gemini(config, images, finding_context, is_single_image=False)
                cleaned_result = remove_step_numbering(result)
                
                # Success - update stats
                if 'processed_images' not in session:
                    session['processed_images'] = 0
                session['processed_images'] += len(images)
                session.modified = True
                
                add_log(f"Successfully generated step using {config['provider']}::{config['model']}", "success")
                return cleaned_result
                
            except Exception as e:
                error_msg = str(e)
                best_error = e
                last_config = config
                
                if is_rate_limit_error(error_msg):
                    add_log(f"Rate limit hit, trying next configuration...", "warning")
                    continue
                else:
                    add_log(f"Non-rate-limit error: {error_msg}", "error")
                    break
    
    # All providers failed
    error_summary = f"All AI providers failed. Last error with {last_config['provider']}::{last_config['model']}: {str(best_error)}"
    add_log(error_summary, "error")
    return f"Error: {error_summary}"


def process_single_image_with_fallback(image, finding_context=None):
    """Process single image with automatic fallback."""
    # Initialize provider trackers if not exist
    if 'provider_usage' not in session:
        session['provider_usage'] = {'gemini': 0}
    
    # Try each provider
    best_error = None
    last_config = None
    
    for provider_name in AI_PROVIDERS.keys():
        session['provider_usage'][provider_name] = session['provider_usage'].get(provider_name, 0) + 1
        
        # Try multiple attempts within each provider
        for attempt in range(MAX_RETRIES * 2):
            try:
                config = get_next_provider_config(provider_name)
                
                add_log(f"Attempting {config['provider']}::{config['model']} with key {config['api_key'][:10]}... (attempt {attempt+1})")
                
                result = generate_with_gemini(config, [image], finding_context, is_single_image=True)
                cleaned_result = remove_step_numbering(result)
                
                # Success - update stats
                if 'processed_images' not in session:
                    session['processed_images'] = 0
                session['processed_images'] += 1
                session.modified = True
                
                add_log(f"Successfully generated step using {config['provider']}::{config['model']}", "success")
                return cleaned_result
                
            except Exception as e:
                error_msg = str(e)
                best_error = e
                last_config = config
                
                if is_rate_limit_error(error_msg):
                    add_log(f"Rate limit hit, trying next configuration...", "warning")
                    continue
                else:
                    add_log(f"Non-rate-limit error: {error_msg}", "error")
                    break
    
    # All providers failed
    error_summary = f"All AI providers failed. Last error with {last_config['provider']}::{last_config['model']}: {str(best_error)}"
    add_log(error_summary, "error")
    return f"Error: {error_summary}"


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
    session['provider_usage'] = {'gemini': 0}
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
                    extracted_step = process_images_with_fallback(images, finding_context)
                    
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
                    extracted_step = process_images_with_fallback(all_images, finding_context)
                    
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

    # Store the uploaded file path in the session
    session['uploaded_file'] = upload_path
    session.modified = True

    return jsonify({
        'success': True,
        'message': 'File uploaded successfully'
    })


@app.route('/process', methods=['POST'])
def process():
    """Start processing the uploaded file."""
    zip_path = session.get('uploaded_file')
    if not zip_path or not os.path.exists(zip_path):
        return jsonify({'error': 'No uploaded file found'}), 400

    # Reset processing state
    session['processing_complete'] = False
    session['output_file_path'] = None
    session['processing_log'] = []
    session['error_count'] = 0
    session['fallback_count'] = 0
    session['successful_requests'] = 0
    session.modified = True

    try:
        output_file = process_notes_zip(zip_path)
        if output_file:
            return jsonify({
                'success': True,
                'message': 'File processed successfully',
                'stats': {
                    'findings': session.get('processed_findings', 0),
                    'steps': session.get('processed_steps', 0),
                    'images': session.get('processed_images', 0)
                }
            })
        else:
            return jsonify({'error': 'Failed to process file'}), 500

    except Exception as e:
        add_log(f"Processing error: {str(e)}", "error")
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500


@app.route('/status')
def status():
    """Get the current processing status."""
    return jsonify({
        'complete': session.get('processing_complete', False),
        'log': session.get('processing_log', []),
        'stats': {
            'findings': session.get('processed_findings', 0),
            'steps': session.get('processed_steps', 0),
            'images': session.get('processed_images', 0)
        },
        'api_usage': session.get('api_key_usage_count', {}),
        'provider_usage': session.get('provider_usage', {}),
        'output_file': session.get('output_file_path')
    })


@app.route('/download')
def download():
    """Download the processed file."""
    output_file = session.get('output_file_path')
    if not output_file or not os.path.exists(output_file):
        return jsonify({'error': 'No processed file available'}), 404

    @after_this_request
    def cleanup(response):
        # Clean up the uploaded file after successful processing and download
        uploaded_file = session.get('uploaded_file')
        if uploaded_file and os.path.exists(uploaded_file):
            try:
                os.remove(uploaded_file)
            except OSError:
                pass
        session.pop('uploaded_file', None)
        session.pop('output_file_path', None)
        return response

    return send_file(output_file, as_attachment=True, download_name='processed_notes.zip')


@app.route('/reset', methods=['POST'])
def reset():
    """Reset the session and clean up files."""
    uploaded_file = session.get('uploaded_file')
    if uploaded_file and os.path.exists(uploaded_file):
        try:
            os.remove(uploaded_file)
        except OSError:
            pass

    output_file = session.get('output_file_path')
    if output_file and os.path.exists(output_file):
        try:
            os.remove(output_file)
        except OSError:
            pass

    session.clear()
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(debug=True)
