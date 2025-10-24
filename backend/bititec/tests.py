import sys
import os
import subprocess

def debug_firewall():
    print("🔧 Firewall Debug Information")
    print("=" * 50)
    
    # Get current Python path
    python_path = sys.executable
    print(f"Current Python: {python_path}")
    print(f"File exists: {os.path.exists(python_path)}")
    
    # Get project directory
    project_dir = os.getcwd()
    print(f"Project dir: {project_dir}")
    
    # Check if the path in your rule exists
    rule_path = r"C:\Users\user\Desktop\B-Systems\BititecSystem\.venv\Scripts\python.exe"
    print(f"Rule path: {rule_path}")
    print(f"Rule path exists: {os.path.exists(rule_path)}")
    
    # Check if paths match
    if os.path.normpath(python_path) != os.path.normpath(rule_path):
        print("❌ PATHS DON'T MATCH! This is likely the issue.")
        print(f"   Actual: {python_path}")
        print(f"   Rule:   {rule_path}")
    else:
        print("✅ Paths match")
    
    # Check firewall rules
    print("\n🛡️ Checking firewall rules...")
    try:
        result = subprocess.run(
            ['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=all'], 
            capture_output=True, 
            text=True
        )
        rules = [line for line in result.stdout.split('\n') if 'Python' in line or 'Django' in line]
        if rules:
            print("Found Python/Django rules:")
            for rule in rules:
                print(f"  {rule.strip()}")
        else:
            print("No Python/Django rules found")
    except Exception as e:
        print(f"Error checking rules: {e}")

if __name__ == "__main__":
    debug_firewall()