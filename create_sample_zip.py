import os
import zipfile

def create_sample_zip():
    """Create a sample notes.zip file for testing."""
    
    # Create a temporary directory structure
    base_dir = 'temp_notes'
    
    # Create parent node: Findings#auth
    auth_dir = os.path.join(base_dir, 'Findings#auth')
    os.makedirs(auth_dir, exist_ok=True)
    
    # Create information.txt with finding description
    with open(os.path.join(auth_dir, 'information.txt'), 'w') as f:
        f.write("""Authorization Bypass Testing

This finding tests for authorization bypass vulnerabilities in the transfer functionality. 
The test involves manipulating account numbers to verify if users can access or modify 
accounts they are not authorized to access.

Test Scenario:
- User tries to initiate a transfer
- Account parameter is intercepted and modified
- System should reject unauthorized access attempts
""")
    
    # Create child node: Findings#auth-1
    auth1_dir = os.path.join(auth_dir, 'Findings#auth-1')
    os.makedirs(auth1_dir, exist_ok=True)
    
    # Create step nodes (1, 2, 3, 4, 5)
    for step_num in [1, 2, 3, 4, 5]:
        step_dir = os.path.join(auth1_dir, str(step_num))
        os.makedirs(step_dir, exist_ok=True)
        
        # Create placeholder images (in real scenario, these would be actual screenshots)
        # For now, we'll create empty .txt files as placeholders
        with open(os.path.join(step_dir, f'screenshot_{step_num}.txt'), 'w') as f:
            f.write(f"[This would be a screenshot image for step {step_num}]\n")
        
        # Create empty description.txt (will be filled by AI)
        with open(os.path.join(step_dir, 'description.txt'), 'w') as f:
            f.write("")
    
    # Create ZIP file
    zip_filename = 'notes.zip'
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, base_dir)
                zipf.write(file_path, arcname)
    
    print(f"✅ Created sample {zip_filename}")
    print("Note: This is a test structure with placeholder files.")
    print("Replace the .txt placeholder files with actual image screenshots (.jpg, .png, etc.) for real usage.")
    
    # Clean up
    import shutil
    shutil.rmtree(base_dir)

if __name__ == '__main__':
    create_sample_zip()
