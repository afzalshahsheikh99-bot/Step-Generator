import os
import zipfile
import json
import base64
from io import BytesIO
from flask import Flask, render_template, request, jsonify, send_from_directory
from PIL import Image
import google.generativeai as genai

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Configure Gemini API
genai.configure(api_key="AIzaSyAb8qYXZWwE8LIX5CFM5geQ0k0FBIt5mCw")
model = genai.GenerativeModel(model_name="gemini-3-pro-preview")

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def analyze_image(image_path, finding_description):
    """Analyze image using Gemini and generate step description."""
    try:
        img = Image.open(image_path)
        
        prompt = f"""You are a security testing assistant. Based on the finding description and the screenshot, generate a detailed step-by-step instruction.

Finding Description: {finding_description}

Analyze the screenshot and write a clear, actionable step that describes what action is being shown or what the user should do next.

Output format: Just the step text, no numbering, no extra explanation.

Examples of good steps:
- "Login with the maker 'Virat_maker1', navigate to 'Transfers' and click on the 'Initiate Transfer'. Click on the 'Single Transfer'."
- "Now, select the 'Debit Account' and the 'Credit Account'."
- "Observe the request and response. Note the parameter 'Accountno' : '1001641537'."
- "Now change the value of parameter 'Accountno' to '1000062974'."
- "Observe the response."

Generate the step:"""

        response = model.generate_content([prompt, img])
        return response.text.strip()
    except Exception as e:
        print(f"Error analyzing image: {e}")
        return f"Error analyzing image: {str(e)}"


def get_all_images(folder_path):
    """Get all image files from a folder."""
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    images = []
    for file in os.listdir(folder_path):
        if os.path.splitext(file)[1].lower() in image_extensions:
            images.append(os.path.join(folder_path, file))
    return sorted(images)


def process_notes_structure(extract_path):
    """Process the notes.zip structure and return a tree."""
    structure = []
    
    if not os.path.exists(extract_path):
        return structure
    
    # Find all parent nodes (Findings#auth type folders)
    items = sorted([item for item in os.listdir(extract_path) 
                   if os.path.isdir(os.path.join(extract_path, item))])
    
    for parent_folder in items:
        parent_path = os.path.join(extract_path, parent_folder)
        
        # Check if this is a parent node (has information.txt)
        info_path = os.path.join(parent_path, 'information.txt')
        finding_description = ""
        
        if os.path.exists(info_path):
            with open(info_path, 'r', encoding='utf-8', errors='ignore') as f:
                finding_description = f.read()
        
        # Find child nodes
        children = []
        child_items = sorted([item for item in os.listdir(parent_path) 
                             if os.path.isdir(os.path.join(parent_path, item))])
        
        for child_folder in child_items:
            child_path = os.path.join(parent_path, child_folder)
            
            # Check if this is a child node (contains numbered folders)
            nodes = []
            node_items = sorted([item for item in os.listdir(child_path) 
                                if os.path.isdir(os.path.join(child_path, item))], 
                               key=lambda x: int(x) if x.isdigit() else float('inf'))
            
            for node_folder in node_items:
                node_path = os.path.join(child_path, node_folder)
                
                # Get all images in this node
                images = get_all_images(node_path)
                
                # Check if description.txt exists
                desc_path = os.path.join(node_path, 'description.txt')
                existing_description = ""
                has_description = os.path.exists(desc_path)
                
                if has_description:
                    with open(desc_path, 'r', encoding='utf-8', errors='ignore') as f:
                        existing_description = f.read()
                
                nodes.append({
                    'id': node_folder,
                    'path': node_path,
                    'images': images,
                    'image_count': len(images),
                    'has_description': has_description,
                    'existing_description': existing_description
                })
            
            children.append({
                'id': child_folder,
                'path': child_path,
                'nodes': nodes,
                'node_count': len(nodes)
            })
        
        structure.append({
            'id': parent_folder,
            'path': parent_path,
            'description': finding_description,
            'children': children,
            'child_count': len(children)
        })
    
    return structure


@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.zip'):
        return jsonify({'error': 'Please upload a .zip file'}), 400
    
    # Clear previous uploads
    for item in os.listdir(app.config['UPLOAD_FOLDER']):
        item_path = os.path.join(app.config['UPLOAD_FOLDER'], item)
        if os.path.isdir(item_path):
            for sub_item in os.listdir(item_path):
                sub_item_path = os.path.join(item_path, sub_item)
                try:
                    if os.path.isfile(sub_item_path):
                        os.unlink(sub_item_path)
                    elif os.path.isdir(sub_item_path):
                        import shutil
                        shutil.rmtree(sub_item_path)
                except:
                    pass
        elif os.path.isfile(item_path):
            try:
                os.unlink(item_path)
            except:
                pass
    
    # Save and extract the file
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], 'notes.zip')
    file.save(upload_path)
    
    extract_path = os.path.join(app.config['UPLOAD_FOLDER'], 'extracted')
    
    # Remove existing extracted folder
    if os.path.exists(extract_path):
        import shutil
        shutil.rmtree(extract_path)
    
    os.makedirs(extract_path, exist_ok=True)
    
    with zipfile.ZipFile(upload_path, 'r') as zip_ref:
        zip_ref.extractall(extract_path)
    
    # Process the structure
    structure = process_notes_structure(extract_path)
    
    return jsonify({
        'success': True,
        'structure': structure,
        'message': f'Successfully uploaded and extracted {len(structure)} finding(s)'
    })


@app.route('/generate', methods=['POST'])
def generate_steps():
    """Generate steps for a specific node using AI."""
    data = request.json
    node_path = data.get('node_path')
    finding_description = data.get('finding_description', '')
    
    if not node_path or not os.path.exists(node_path):
        return jsonify({'error': 'Invalid node path'}), 400
    
    # Get all images in the node
    images = get_all_images(node_path)
    
    if not images:
        return jsonify({'error': 'No images found in this node'}), 400
    
    # Analyze each image and generate steps
    generated_steps = []
    all_steps_text = []
    
    for idx, image_path in enumerate(images, 1):
        step = analyze_image(image_path, finding_description)
        generated_steps.append({
            'image_index': idx,
            'image_path': image_path,
            'step': step
        })
        all_steps_text.append(f"{idx}) {step}")
    
    # Combine all steps
    combined_steps = '\n'.join(all_steps_text)
    
    # Write to description.txt
    desc_path = os.path.join(node_path, 'description.txt')
    with open(desc_path, 'w', encoding='utf-8') as f:
        f.write(combined_steps)
    
    return jsonify({
        'success': True,
        'steps': generated_steps,
        'combined_steps': combined_steps,
        'message': f'Successfully generated steps for {len(images)} image(s)'
    })


@app.route('/preview_image')
def preview_image():
    """Preview an image."""
    image_path = request.args.get('path')
    if not image_path or not os.path.exists(image_path):
        return jsonify({'error': 'Image not found'}), 404
    
    # Convert image to base64
    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    
    # Get file extension for mime type
    ext = os.path.splitext(image_path)[1].lower()
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp'
    }
    
    return jsonify({
        'image': f"data:{mime_types.get(ext, 'image/jpeg')};base64,{image_data}",
        'filename': os.path.basename(image_path)
    })


@app.route('/download_zip')
def download_zip():
    """Download the modified notes.zip file."""
    zip_path = os.path.join(app.config['UPLOAD_FOLDER'], 'notes.zip')
    
    # Create a new zip with updated content
    extract_path = os.path.join(app.config['UPLOAD_FOLDER'], 'extracted')
    new_zip_path = os.path.join(app.config['UPLOAD_FOLDER'], 'notes_updated.zip')
    
    with zipfile.ZipFile(new_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(extract_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, extract_path)
                zipf.write(file_path, arcname)
    
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        'notes_updated.zip',
        as_attachment=True,
        download_name='notes.zip'
    )


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
