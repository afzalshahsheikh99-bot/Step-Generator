import google.generativeai as genai
from PIL import Image
import os
import io
import base64
import zipfile
import shutil
import glob
import re
import streamlit as st
import tempfile
import time
from datetime import datetime

# Configure page settings for better appearance
st.set_page_config(
    page_title="Notes.zip Processor",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #2563EB;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .card {
        padding: 1.5rem;
        border-radius: 0.5rem;
        background-color: #F3F4F6;
        margin-bottom: 1rem;
    }
    .success-message {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #D1FAE5;
        border-left: 5px solid #10B981;
        margin: 1rem 0;
    }
    .info-message {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #E0F2FE;
        border-left: 5px solid #0EA5E9;
        margin: 1rem 0;
    }
    .warning-message {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #FEF3C7;
        border-left: 5px solid #F59E0B;
        margin: 1rem 0;
    }
    .error-message {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #FEE2E2;
        border-left: 5px solid #EF4444;
        margin: 1rem 0;
    }
    .stButton button {
        background-color: #2563EB;
        color: white;
        font-weight: 600;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 0.25rem;
        transition: all 0.3s ease;
    }
    .stButton button:hover {
        background-color: #1D4ED8;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }
    .stDownloadButton button {
        background-color: #059669;
        color: white;
        font-weight: 600;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 0.25rem;
        transition: all 0.3s ease;
    }
    .stDownloadButton button:hover {
        background-color: #047857;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }
    .upload-section {
        border: 2px dashed #CBD5E1;
        border-radius: 0.5rem;
        padding: 2rem;
        text-align: center;
        margin: 1.5rem 0;
    }
    .log-container {
        max-height: 400px;
        overflow-y: auto;
        background-color: #F8FAFC;
        padding: 1rem;
        border-radius: 0.25rem;
        border: 1px solid #E2E8F0;
        font-family: monospace;
        font-size: 0.875rem;
    }
    .step-item {
        padding: 0.5rem;
        margin: 0.25rem 0;
        border-radius: 0.25rem;
        background-color: #EFF6FF;
    }
    .footer {
        margin-top: 3rem;
        text-align: center;
        color: #64748B;
        font-size: 0.875rem;
    }
</style>
""", unsafe_allow_html=True)

# List of API keys - replace these with your actual API keys
API_KEYS = [
    'AIzaSyDlrfOJuTZP_V1-70GMcEo9vtWdpRFFmjY',  # Original key
    'AIzaSyDMvynC96au-ztynqSCGu5XGHO2JS-i10I',      # Replace with your key
    'AIzaSyDltA-iPM00e1C3dWOVRcWwjcvXR2mmp7w',      # Replace with your key
    'AIzaSyCbS4t9oOjvqAyAoCa5oEmlbdd9_2jv0yE',      # Replace with your key
    'AIzaSyDq6y5ZhxRX76w_XFgTPuG8wuc35gHP_74'       # Replace with your key
]

# Initialize the current API key index
if 'current_api_key_index' not in st.session_state:
    st.session_state.current_api_key_index = 0

# Model name for Gemini
MODEL_NAME = 'gemini-2.5-flash'

# Create a session state to track the app state
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
if 'processing_log' not in st.session_state:
    st.session_state.processing_log = []
if 'output_file_path' not in st.session_state:
    st.session_state.output_file_path = None
if 'start_time' not in st.session_state:
    st.session_state.start_time = None
if 'show_logs' not in st.session_state:
    st.session_state.show_logs = False
if 'processed_findings' not in st.session_state:
    st.session_state.processed_findings = 0
if 'processed_steps' not in st.session_state:
    st.session_state.processed_steps = 0
if 'processed_images' not in st.session_state:
    st.session_state.processed_images = 0
if 'api_key_usage_count' not in st.session_state:
    st.session_state.api_key_usage_count = {key: 0 for key in API_KEYS}


def get_next_api_key():
    """Get the next API key in the rotation and configure Gemini with it."""
    current_key = API_KEYS[st.session_state.current_api_key_index]
    
    # Move to the next key for the next request
    st.session_state.current_api_key_index = (st.session_state.current_api_key_index + 1) % len(API_KEYS)
    
    # Track API key usage
    st.session_state.api_key_usage_count[current_key] = st.session_state.api_key_usage_count.get(current_key, 0) + 1
    
    # Configure Gemini with the current key
    genai.configure(api_key=current_key)
    
    add_log(f"Using API key {st.session_state.current_api_key_index} for this request")
    return current_key


def add_log(message, level='info'):
    """Add a log message with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.processing_log.append({
        'timestamp': timestamp,
        'message': message,
        'level': level
    })


def remove_step_numbering(text):
    """Remove step numbering (like '1. ') from the beginning of text."""
    # Match patterns like "1. ", "Step 1: ", "Step 1. ", etc.
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
            # If only one image, process it normally
            return process_single_image_with_gemini(images[0], finding_context)
        
        # Get the next API key in the rotation
        current_api_key = get_next_api_key()
        
        # Create the Gemini model
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
        
        # Improved prompt for multiple images with finding context
        context_section = ""
        if finding_context:
            context_section = f"""
**FINDING CONTEXT:**
{finding_context}

**IMPORTANT:** Use this context to understand the security vulnerability being tested. Your step should be relevant to this specific finding.

"""
        
        prompt = f"""
{context_section}You are analyzing screenshots from a security assessment. Generate a clear, actionable test step based on what you observe.

**Instructions:**
1. **Analyze the context** (if provided) to understand the security issue being tested.
2. **Examine ALL images** together to understand the complete sequence of actions.
3. **Focus on key elements** shown in the screenshots:
   - Form fields, buttons, links that are emphasized or boxed
   - HTTP requests/responses with important parameters
   - Application screens, login forms, navigation elements
   - Values, tokens, or data being captured or modified
4. **Generate ONE consolidated step** that captures the essential actions shown across all images.
5. **Writing requirements**:
   - Maximum 1-2 sentences
   - Use imperative mood (Login, Navigate, Observe, Change, Click, etc.)
   - Be specific about field names, parameter names, and values
   - Include element names in quotes when relevant
   - Connect related actions with "and"
6. **Example patterns**:
   - "Login with username 'admin' and click 'Submit' button"
   - "Change parameter 'id' to '1' and submit the request"
   - "Navigate to 'Settings' section and observe the response headers"
   - "Capture the session token from the response body"
7. **Avoid**:
   - Step numbers or prefixes
   - Long explanations or verbose descriptions
   - Splitting into multiple steps
   - Unnecessary details

Return only a short, clear step description based on the key elements visible in the screenshots.
"""
        
        # Create a request with all images
        response_parts = [prompt]
        response_parts.extend(image_parts)
        
        response = model.generate_content(response_parts)
        
        # Increment processed images count
        st.session_state.processed_images += len(images)
        
        # Clean up the response by removing any numbering
        cleaned_response = remove_step_numbering(response.text)
        
        # Return the cleaned text response
        return cleaned_response
        
    except Exception as e:
        # If there's an error, try with the next API key
        add_log(f"Error with API key {st.session_state.current_api_key_index-1}: {str(e)}", "error")
        
        # Only retry once to avoid infinite loops
        if "retry_count" not in locals():
            retry_count = 1
            add_log(f"Retrying with next API key...", "warning")
            return process_images_with_gemini(images, finding_context)
        else:
            add_log(f"Failed after retry. Error processing images: {str(e)}", "error")
            return f"Error processing images: {str(e)}"


def process_single_image_with_gemini(image, finding_context=None):
    """Process a single image with Gemini API and return steps."""
    try:
        # Get the next API key in the rotation
        current_api_key = get_next_api_key()
        
        # Convert the image to bytes for Gemini
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format=image.format if image.format else 'JPEG')
        img_bytes = img_byte_arr.getvalue()
        
        # Create the Gemini model with hardcoded model name
        model = genai.GenerativeModel(MODEL_NAME)
        
        # Improved prompt for single image with finding context
        context_section = ""
        if finding_context:
            context_section = f"""
**FINDING CONTEXT:**
{finding_context}

**IMPORTANT:** Use this context to understand the security vulnerability being tested. Your step should be relevant to this specific finding.

"""
        
        prompt = f"""
{context_section}You are analyzing a screenshot from a security assessment. Create one clear step that describes what action is being performed.

**Analysis Instructions:**
1. **Consider the finding context** (if provided) to ensure your step is relevant to the specific security issue.
2. **Identify key elements** in the image:
   - Emphasized, boxed, or visually distinct form fields, buttons, links
   - Important HTTP requests, responses, headers, or parameters
   - Application screens, login forms, navigation sections
   - Values, tokens, or data being captured or modified
3. **Create ONE clear step** that describes the main action or observation.
4. **Requirements:**
   - Use clear, specific wording
   - Reference the security context when relevant
   - Include field names, parameter names, and values in quotes
   - Use imperative mood (Observe, Login, Modify, Click, etc.)
   - Maximum 1-2 sentences
5. **Example formats:**
   - "Observe the request parameters for SQL injection vulnerabilities"
   - "Login with valid credentials and navigate to the admin panel"
   - "Modify parameter 'user_id' to test for authorization bypass"
   - "Capture the authentication token from the response headers"

**Important:** Do not include step numbers, explanations, or multiple instructions. Return only the single step description.
"""
        
        # Create a request with the image
        response = model.generate_content([
            prompt,
            {"mime_type": f"image/{image.format.lower() if image.format else 'jpeg'}", 
             "data": base64.b64encode(img_bytes).decode('utf-8')}
        ])
        
        # Increment processed images count
        st.session_state.processed_images += 1
        
        # Clean up the response by removing any numbering
        cleaned_response = remove_step_numbering(response.text)
        
        # Return the cleaned text response
        return cleaned_response
        
    except Exception as e:
        # If there's an error, try with the next API key
        add_log(f"Error with API key {st.session_state.current_api_key_index-1}: {str(e)}", "error")
        
        # Only retry once to avoid infinite loops
        if "retry_count" not in locals():
            retry_count = 1
            add_log(f"Retrying with next API key...", "warning")
            return process_single_image_with_gemini(image, finding_context)
        else:
            add_log(f"Failed after retry. Error processing image: {str(e)}", "error")
            return f"Error processing image: {str(e)}"


def find_image_files(directory):
    """Find all image files in a directory."""
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']
    image_files = []
    
    for ext in image_extensions:
        image_files.extend(glob.glob(os.path.join(directory, '*' + ext)))
    
    return image_files


def process_notes_zip(uploaded_zip):
    """Process the notes.zip file according to the specified structure."""
    # Reset counters
    st.session_state.processed_findings = 0
    st.session_state.processed_steps = 0
    st.session_state.processed_images = 0
    st.session_state.api_key_usage_count = {key: 0 for key in API_KEYS}
    
    # Create a temporary directory for extraction
    temp_dir = tempfile.mkdtemp(prefix="temp_extracted_notes_")
    output_file = None
    
    try:
        # Save the uploaded zip file to a temporary location
        zip_path = os.path.join(temp_dir, "notes.zip")
        with open(zip_path, "wb") as f:
            f.write(uploaded_zip.getbuffer())
        
        # Extract the zip file
        add_log(f"Extracting zip file...")
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Process the extracted files
        add_log("Processing files...")
        process_findings(extract_dir)
        
        # Repack the zip file
        add_log("Repacking the zip file...")
        output_file = os.path.join(temp_dir, "processed_notes.zip")
        repack_zip(extract_dir, output_file)
        
        add_log("Processing complete!", "success")
        
        # Return the path to the output file
        return output_file
        
    except Exception as e:
        add_log(f"Error processing the zip file: {str(e)}", "error")
        return None
    
    finally:
        # We'll clean up the temp directory later after the file has been downloaded
        pass


def process_special_folder(special_folder, finding_name, finding_context=None):
    """Process special folders ending with -1, -2, etc."""
    add_log(f"Processing special folder: {os.path.basename(special_folder)} in finding {finding_name}")
    
    # Look for folder 1 within the special folder
    folder_1_path = os.path.join(special_folder, "1")
    if os.path.exists(folder_1_path) and os.path.isdir(folder_1_path):
        # Now look for another folder 1 within folder 1
        inner_folder_1_path = os.path.join(folder_1_path, "1")
        if os.path.exists(inner_folder_1_path) and os.path.isdir(inner_folder_1_path):
            # Find all images in this inner folder 1
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
                    
                    # Write the step to description.txt in folder 1
                    desc_file_special = os.path.join(folder_1_path, "Description.txt")
                    with open(desc_file_special, 'w') as f:
                        f.write(extracted_step)
                    
                    add_log(f"Updated description.txt in special path {os.path.basename(special_folder)}/1 with context-aware extracted step")
                    return True
    
    add_log(f"No valid images found or invalid path structure in special folder {os.path.basename(special_folder)}", "warning")
    return False


def process_findings(base_dir):
    """Process all findings in the notes directory."""
    # Look for finding directories
    finding_dirs = [d for d in glob.glob(os.path.join(base_dir, "*")) if os.path.isdir(d)]
    
    add_log(f"Found {len(finding_dirs)} finding directories")
    
    # Create progress bar
    progress_bar = st.progress(0)
    total_findings = len(finding_dirs)
    
    for i, finding_dir in enumerate(finding_dirs):
        finding_name = os.path.basename(finding_dir)
        add_log(f"Processing finding: {finding_name}")
        st.session_state.processed_findings += 1
        
        # Read the information.txt file from the parent finding directory
        finding_context = read_finding_information(finding_dir)
        if finding_context:
            add_log(f"Using finding context for {finding_name}: {finding_context[:100]}...")
        
        # Find special folders (ending with -1, -2, etc.) in the finding directory
        special_folders = [d for d in glob.glob(os.path.join(finding_dir, "*-*")) 
                         if os.path.isdir(d) and re.match(r'.*-\d+$', os.path.basename(d))]
        
        if special_folders:
            add_log(f"Found {len(special_folders)} special folders in finding {finding_name}")
            for special_folder in special_folders:
                process_special_folder(special_folder, finding_name, finding_context)
        
        # Find step directories inside the finding directory and its child directories
        step_dirs = []
        for root, dirs, files in os.walk(finding_dir):
            for dir_name in dirs:
                if re.match(r'^\d+$', dir_name):  # If directory name is just a number
                    step_dirs.append(os.path.join(root, dir_name))
        
        # Sort step directories by their numeric name
        step_dirs.sort(key=lambda x: int(os.path.basename(x)))
        
        total_steps = len(step_dirs)
        processed_steps = 0
        
        for step_dir in step_dirs:
            step_num = os.path.basename(step_dir)
            add_log(f"Processing step {step_num} with finding context")
            st.session_state.processed_steps += 1
            
            # Find the description.txt file
            desc_file = os.path.join(step_dir, "Description.txt")
            
            # Find image folders (numbered folders)
            image_folders = [d for d in glob.glob(os.path.join(step_dir, "*")) 
                            if os.path.isdir(d) and re.match(r'^\d+$', os.path.basename(d))]
            
            if image_folders:
                # Sort image folders by their numeric name
                image_folders.sort(key=lambda x: int(os.path.basename(x)))
                
                # Process images from all folders
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
                    add_log(f"Processing {len(all_images)} images for step {step_num} with finding context")
                    
                    # Process with Gemini using finding context
                    extracted_step = process_images_with_gemini(all_images, finding_context)
                    
                    # Write the step to description.txt
                    with open(desc_file, 'w') as f:
                        f.write(extracted_step)
                    
                    add_log(f"Updated description.txt with context-aware extracted step")
                else:
                    add_log(f"No valid images found in step {step_num}", "warning")
            else:
                add_log(f"No image folders found in step {step_num}", "warning")
            
            processed_steps += 1
            
            # Update progress
            current_progress = (i / total_findings) + (processed_steps / total_steps / total_findings)
            progress_bar.progress(min(current_progress, 1.0))
            
            # Yield to the UI thread to update the progress bar
            time.sleep(0.01)


def repack_zip(source_dir, output_zip):
    """Repack the processed directory back into a zip file."""
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_dir)
                zipf.write(file_path, arcname)


def main():
    # Sidebar with app info and settings
    with st.sidebar:
        st.markdown("### About")
        st.markdown("""
        This application processes a notes.zip file containing security assessment images.
        It analyzes images using Google's Gemini AI and writes consolidated steps to description.txt files.
        
        **Enhanced Features:**
        - Reads finding context from information.txt files
        - Generates context-aware test steps
        - Supports parent-child finding structure
        """)
        
        st.markdown("---")
        
        st.markdown("### Settings")
        log_toggle = st.checkbox("Show detailed logs", value=st.session_state.show_logs)
        if log_toggle != st.session_state.show_logs:
            st.session_state.show_logs = log_toggle
            st.rerun()
        
        st.markdown("---")
        
        st.markdown("### Statistics")
        if st.session_state.processing_complete:
            st.markdown(f"""
            - **Findings processed:** {st.session_state.processed_findings}
            - **Steps processed:** {st.session_state.processed_steps}
            - **Images analyzed:** {st.session_state.processed_images}
            """)
            
            # Display API key usage statistics
            st.markdown("### API Key Usage")
            for idx, (key, count) in enumerate(st.session_state.api_key_usage_count.items()):
                st.markdown(f"- **API Key {idx+1}:** {count} requests")
            
            # Calculate processing time
            if st.session_state.start_time:
                elapsed_time = time.time() - st.session_state.start_time
                minutes, seconds = divmod(elapsed_time, 60)
                st.markdown(f"**Processing time:** {int(minutes)}m {int(seconds)}s")
    
    # Main content area
    st.markdown('<h1 class="main-header">Enhanced Notes.zip Processor</h1>', unsafe_allow_html=True)
    
    # Create two columns for the hero section
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("""
        This enhanced tool processes security assessment notes by:
        1. Reading finding context from information.txt files
        2. Extracting step information from security test screenshots
        3. Using AI to generate context-aware, consistent step descriptions 
        4. Writing the descriptions back to the file structure
        """)
    
    with col2:
        st.markdown("""
        <div style="background-color:#F0F9FF; padding:15px; border-radius:5px; border-left:5px solid #0EA5E9;">
        <h4 style="margin-top:0;">💡 Enhanced Features</h4>
        <p>Now reads information.txt files to provide context-aware step generation based on specific security findings.</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Upload section with custom styling
    st.markdown('<div class="upload-section">', unsafe_allow_html=True)
    st.markdown("### Upload your notes.zip file")
    uploaded_file = st.file_uploader("Choose a ZIP file", type=["zip"], label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # If file uploaded but not processed yet
    if uploaded_file is not None and not st.session_state.processing_complete:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"**File uploaded:** {uploaded_file.name}")
        
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("🚀 Process File", type="primary"):
                st.session_state.start_time = time.time()
                st.session_state.processing_complete = False
                st.session_state.processing_log = []
                
                # Create a placeholder for live updates
                status_placeholder = st.empty()
                log_placeholder = st.empty()
                
                with st.spinner("Processing your notes.zip file..."):
                    # Process the file
                    output_path = process_notes_zip(uploaded_file)
                    
                    if output_path:
                        st.session_state.output_file_path = output_path
                        st.session_state.processing_complete = True
                        st.success("✅ Processing completed successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Processing failed. Check the logs for details.")
        
        with col2:
            file_size = len(uploaded_file.getbuffer()) / (1024 * 1024)
            st.metric("File Size", f"{file_size:.2f} MB")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # If processing is complete, show download section
    if st.session_state.processing_complete and st.session_state.output_file_path:
        st.markdown('<div class="success-message">', unsafe_allow_html=True)
        st.markdown("### ✅ Processing Complete!")
        st.markdown("Your notes.zip file has been successfully processed with context-aware step descriptions.")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Create download section
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # Read the processed file for download
            try:
                with open(st.session_state.output_file_path, 'rb') as f:
                    processed_file_data = f.read()
                
                st.download_button(
                    label="📥 Download Processed File",
                    data=processed_file_data,
                    file_name="processed_notes.zip",
                    mime="application/zip",
                    type="primary"
                )
            except Exception as e:
                st.error(f"Error preparing download: {str(e)}")
        
        with col2:
            if st.button("🔄 Process Another File"):
                # Reset session state
                st.session_state.processing_complete = False
                st.session_state.processing_log = []
                st.session_state.output_file_path = None
                st.session_state.start_time = None
                st.session_state.processed_findings = 0
                st.session_state.processed_steps = 0
                st.session_state.processed_images = 0
                st.session_state.api_key_usage_count = {key: 0 for key in API_KEYS}
                st.rerun()
    
    # Show processing logs if enabled
    if st.session_state.show_logs and st.session_state.processing_log:
        st.markdown('<h2 class="sub-header">Processing Logs</h2>', unsafe_allow_html=True)
        
        # Create a container for logs
        log_container = st.container()
        with log_container:
            st.markdown('<div class="log-container">', unsafe_allow_html=True)
            
            # Display logs in reverse order (newest first)
            for log_entry in reversed(st.session_state.processing_log[-50:]):  # Show last 50 logs
                level_color = {
                    'info': '#64748B',
                    'success': '#059669',
                    'warning': '#F59E0B',
                    'error': '#EF4444'
                }.get(log_entry['level'], '#64748B')
                
                st.markdown(
                    f'<div style="color: {level_color}; margin-bottom: 5px;">'
                    f'[{log_entry["timestamp"]}] {log_entry["message"]}'
                    f'</div>',
                    unsafe_allow_html=True
                )
            
            st.markdown('</div>', unsafe_allow_html=True)
    
    # Instructions section
    if not uploaded_file:
        st.markdown('<h2 class="sub-header">📋 Instructions</h2>', unsafe_allow_html=True)
        
        instructions_col1, instructions_col2 = st.columns([1, 1])
        
        with instructions_col1:
            st.markdown("""
            **Expected File Structure:**
            ```
            notes.zip
            ├── Finding1/
            │   ├── information.txt
            │   ├── 1/
            │   │   ├── 1/ (images)
            │   │   └── Description.txt
            │   └── Finding1-1/
            │       └── 1/
            │           └── 1/ (images)
            └── Finding2/
                ├── information.txt
                └── steps...
            ```
            """)
        
        with instructions_col2:
            st.markdown("""
            **Process Overview:**
            1. Upload your notes.zip file
            2. The tool reads information.txt for context
            3. AI analyzes screenshots in numbered folders
            4. Context-aware steps are generated
            5. Description.txt files are updated
            6. Download the processed zip file
            """)
        
        # Feature highlights
        st.markdown('<h2 class="sub-header">🌟 Key Features</h2>', unsafe_allow_html=True)
        
        feature_col1, feature_col2, feature_col3 = st.columns(3)
        
        with feature_col1:
            st.markdown("""
            <div class="card">
            <h4>🧠 Context-Aware Processing</h4>
            <p>Reads information.txt files to understand the security finding context and generates relevant test steps.</p>
            </div>
            """, unsafe_allow_html=True)
        
        with feature_col2:
            st.markdown("""
            <div class="card">
            <h4>🔄 API Key Rotation</h4>
            <p>Automatically rotates between multiple Gemini API keys to handle large processing volumes.</p>
            </div>
            """, unsafe_allow_html=True)
        
        with feature_col3:
            st.markdown("""
            <div class="card">
            <h4>📊 Detailed Statistics</h4>
            <p>Track processing progress with real-time statistics on findings, steps, and images processed.</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Footer
    st.markdown('<div class="footer">', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("""
    **Enhanced Notes.zip Processor** | Powered by Google Gemini AI  
    Built for security assessment workflow automation with context-aware step generation.
    """)
    st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
