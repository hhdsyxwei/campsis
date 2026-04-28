import os
import re

total_lines = 0
file_count = 0

def count_lines(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Count non-empty, non-comment lines
            code_lines = [line for line in lines if line.strip() and not line.strip().startswith('#')]
            return len(code_lines)
    except Exception as e:
        return 0

def analyze_directory(directory):
    global total_lines, file_count
    
    for root, dirs, files in os.walk(directory):
        # Skip hidden directories and cache folders
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'venv', 'env']]
        
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                lines = count_lines(file_path)
                total_lines += lines
                file_count += 1
                print(f"{file_path}: {lines}")

def count_project_code():
    """Count project code lines"""
    global total_lines, file_count
    total_lines = 0
    file_count = 0
    
    print("Counting project code lines...")
    analyze_directory('.')
    
    print(f"\nTotal Python files: {file_count}")
    print(f"Total code lines: {total_lines}")
    
    return {
        'total_files': file_count,
        'total_lines': total_lines
    }

if __name__ == "__main__":
    count_project_code()
