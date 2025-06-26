#!/usr/bin/env python3
"""
SMS Email Bridge
Simple bridge between SMS and Email using IMAP/SMTP
"""

import imaplib
import smtplib
import email
import re
import sys
import os
import subprocess
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# =============================================================================
# CONFIGURATION
# =============================================================================

# The email that will handle forwarding SMS messages
EMAIL_USER = "sms@my-email.com"
EMAIL_PASS = "your-password"

# The email to send SMS messages to
DESTINATION_EMAIL = "your-email@gmail.com"

SMTP_SERVER = "smtp.my-domain.com"
SMTP_PORT = 587
IMAP_SERVER = "imap.my-domain.com"
IMAP_PORT = 993

HOME_DIR = "/data/data/com.termux/files/home"
MAIL_DIR = f"{HOME_DIR}/mail"
LOG_FILE = f"{HOME_DIR}/sms_bridge.log"

# Create mail directory
os.makedirs(MAIL_DIR, exist_ok=True)

# =============================================================================
# SEND SMS TO EMAIL
# =============================================================================
def send_sms_to_email(phone, name, message):
    """Forward SMS to email"""
    try:
        print(f"Sending email for SMS from {phone}...")
        
        if name and name != "Unknown":
            subject = f"SMS from {name} ({phone})"
        else:
            subject = f"SMS from {phone}"
        
        # Create email content
        email_body = f"""{message}

Time: {datetime.now()}

---
Reply to this email to send SMS back to {phone}
"""
        
        print(f"Connecting to SMTP server {SMTP_SERVER}:{SMTP_PORT}...")
        
        # Use msmtp with config file
        msmtp_command = ['msmtp', DESTINATION_EMAIL]
        
        # Create full email with headers
        full_email = f"""From: {EMAIL_USER}
To: {DESTINATION_EMAIL}
Subject: {subject}

{email_body}"""
        
        print("Sending via msmtp...")
        result = subprocess.run(msmtp_command, input=full_email, text=True, 
                              capture_output=True, timeout=30)
        
        if result.returncode == 0:
            print(f"Email sent successfully to {DESTINATION_EMAIL}")
            
            # Log the action
            with open(LOG_FILE, 'a') as f:
                f.write(f"{datetime.now()}: SMS forwarded - From: {phone}, Message: {message[:50]}...\n")
            
            return True
        else:
            print(f"msmtp error: {result.stderr}")
            return False
        
    except subprocess.TimeoutExpired:
        print("Email sending timed out")
        return False
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# =============================================================================
# CHECK FOR EMAIL REPLIES
# =============================================================================
def check_email_replies(quiet_mode=False, search_all=False):
    """Check for email replies and extract content"""
    try:
        if not quiet_mode:
            print("Checking for email replies...")
        
        # Connect to IMAP server
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select('INBOX')
        
        # Search for emails
        if search_all:
            search_criteria = 'SUBJECT "SMS from"'
            if not quiet_mode:
                print("Searching for all SMS emails (read and unread)...")
        else:
            search_criteria = 'UNSEEN SUBJECT "SMS from"'
            if not quiet_mode:
                print("Searching for unread SMS emails only...")
        
        status, messages = mail.search(None, search_criteria)
        
        if status != 'OK' or not messages[0]:
            if not quiet_mode:
                if search_all:
                    print("No SMS emails found at all")
                else:
                    print("No unread SMS replies found")
            mail.close()
            mail.logout()
            return []
        
        msg_ids = messages[0].decode().split()
        
        if not quiet_mode:
            print(f"Found {len(msg_ids)} email replies")
        
        results = []
        
        for msg_id in msg_ids:
            if not quiet_mode:
                print(f"Processing message {msg_id}...")
            
            # Fetch the email
            status, data = mail.fetch(msg_id, '(RFC822)')
            
            if status == 'OK' and data and data[0]:
                email_content = data[0][1].decode('utf-8', errors='ignore')
                
                # Parse the email
                msg = email.message_from_string(email_content)
                
                # Extract phone number from subject
                subject = msg.get('Subject', '')
                phone_match = re.search(r'(\+?[0-9]{10,15})', subject)
                if not phone_match:
                    if not quiet_mode:
                        print(f"Could not extract phone number from: {subject}")
                    continue
                
                phone = phone_match.group(1)
                
                # Extract message content
                message_content = extract_message_content(msg)
                
                if phone and message_content:
                    # Encode newlines for Tasker compatibility
                    encoded_message = message_content.replace('\n', '\\n')
                    result = f"REPLY_FOUND: {phone}|||{encoded_message}"
                    print(result)
                    
                    if not quiet_mode:
                        print(f"  -> To: {phone}")
                        print(f"  -> Message: {message_content}")  # Show original with real newlines
                    
                    # Mark as read (only if it was unread)
                    if not search_all:
                        mail.store(msg_id, '+FLAGS', r'\Seen')
                    
                    # Log the result
                    with open(LOG_FILE, 'a') as f:
                        f.write(f"{datetime.now()}: Parsed reply - To: {phone}, Message: {message_content[:50]}...\n")
                    
                    results.append((phone, message_content))
                    
                    # Process only one message at a time for normal operation
                    if not search_all:
                        break
                else:
                    if not quiet_mode:
                        print(f"Failed to extract content from message {msg_id}")
        
        mail.close()
        mail.logout()
        return results
        
    except Exception as e:
        if not quiet_mode:
            print(f"Error checking emails: {e}")
        return []

def extract_message_content(msg):
    """Extract the user's message content from email"""
    message_content = ''
    
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                content = part.get_payload(decode=True)
                if content:
                    try:
                        content = content.decode('utf-8', errors='ignore')
                    except:
                        content = str(content)
                    
                    message_content = parse_text_content(content)
                    if message_content:
                        break
    else:
        content = msg.get_payload(decode=True)
        if content:
            try:
                content = content.decode('utf-8', errors='ignore')
            except:
                content = str(content)
            
            message_content = parse_text_content(content)
    
    return message_content

def parse_text_content(content):
    """Parse text content to find user's actual message"""
    lines = content.split('\n')
    message_lines = []
    found_start = False
    
    for line in lines:
        line_stripped = line.strip()
        
        # Skip empty lines at the beginning
        if not found_start and not line_stripped:
            continue
        
        # Stop at quoted content or email signatures
        if line_stripped.startswith('>') or 'wrote:' in line_stripped.lower():
            break
        
        # Stop at email signatures or footers
        if any(marker in line_stripped.lower() for marker in ['--', '___', 'sent from', 'get outlook']):
            break
        
        # Skip email headers that might be in body
        if any(line_stripped.startswith(h) for h in ['From:', 'To:', 'Subject:', 'Date:', 'Return-Path:']):
            continue
        
        # If we find a line with letters, start collecting
        if re.search(r'[A-Za-z]', line_stripped) and len(line_stripped) > 0:
            found_start = True
            message_lines.append(line_stripped)
        elif found_start:
            # If we've started collecting and hit an empty line, 
            # include it but check if next line continues the message
            if not line_stripped:
                # Look ahead to see if there's more content
                remaining_lines = lines[lines.index(line) + 1:]
                has_more_content = any(
                    re.search(r'[A-Za-z]', l.strip()) and 
                    not l.strip().startswith('>') and 
                    'wrote:' not in l.lower()
                    for l in remaining_lines[:3]  # Look ahead 3 lines
                )
                if has_more_content:
                    message_lines.append('')  # Include the empty line
                else:
                    break  # End of message
            else:
                message_lines.append(line_stripped)
    
    # Join the message lines and clean up
    if message_lines:
        full_message = '\n'.join(message_lines).strip()
        # Remove excessive newlines
        full_message = re.sub(r'\n{3,}', '\n\n', full_message)
        return full_message
    
    return ''

# =============================================================================
# DEBUG EMAIL PARSING
# =============================================================================
def debug_email(search_all=False):
    """Debug email parsing issues"""
    try:
        # Search criteria
        search_criteria = 'SUBJECT "SMS from"' if search_all else 'UNSEEN SUBJECT "SMS from"'
        print(f"Searching for emails with criteria: {search_criteria}")
        
        # Connect to IMAP
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select('INBOX')
        
        status, messages = mail.search(None, search_criteria)
        
        if status != 'OK' or not messages[0]:
            print("No emails found")
            mail.close()
            mail.logout()
            return
        
        msg_ids = messages[0].decode().split()
        print(f"Found {len(msg_ids)} email(s)")
        
        # Debug first message
        msg_id = msg_ids[0]
        print(f"\n=== DEBUGGING MESSAGE {msg_id} ===")
        
        status, data = mail.fetch(msg_id, '(RFC822)')
        
        if status == 'OK' and data and data[0]:
            email_content = data[0][1].decode('utf-8', errors='ignore')
            print(f"Successfully fetched email: {len(email_content)} bytes")
            
            # Parse and show structure
            msg = email.message_from_string(email_content)
            print(f"Subject: {msg.get('Subject', '')}")
            print(f"Is multipart: {msg.is_multipart()}")
            
            if msg.is_multipart():
                print("\nParts:")
                for i, part in enumerate(msg.walk()):
                    print(f"  Part {i}: {part.get_content_type()}")
                    if part.get_content_type() == 'text/plain':
                        content = part.get_payload(decode=True)
                        if content:
                            content = content.decode('utf-8', errors='ignore')
                            lines = content.split('\n')
                            print(f"    Text content found: {len(lines)} lines")
                            for j, line in enumerate(lines[:5]):
                                print(f"      Line {j}: {repr(line.strip())}")
                            break
            else:
                content = msg.get_payload(decode=True)
                if content:
                    content = content.decode('utf-8', errors='ignore')
                    lines = content.split('\n')
                    print(f"Single part content: {len(lines)} lines")
                    for j, line in enumerate(lines[:5]):
                        print(f"  Line {j}: {repr(line.strip())}")
        
        mail.close()
        mail.logout()
        print("========================")
        
    except Exception as e:
        print(f"Debug error: {e}")

# =============================================================================
# SETUP
# =============================================================================
def setup():
    """Setup SMS Email Bridge"""
    print("Setting up SMS Email Bridge...")
    
    # Install packages
    try:
        subprocess.run(['pkg', 'update'], check=True)
        subprocess.run(['pkg', 'install', '-y', 'python', 'msmtp'], check=True)
        print("Packages installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Package installation failed: {e}")
    
    # Create msmtp config
    msmtp_config = f"""account default
host {SMTP_SERVER}
port {SMTP_PORT}
auth on
tls on
tls_starttls off
user {EMAIL_USER}
passwordeval echo {EMAIL_PASS}
from {EMAIL_USER}
logfile {HOME_DIR}/.msmtp.log
"""
    
    config_file = f"{HOME_DIR}/.msmtprc"
    try:
        with open(config_file, 'w') as f:
            f.write(msmtp_config)
        os.chmod(config_file, 0o600)
        print(f"Created msmtp config: {config_file}")
    except Exception as e:
        print(f"Warning: Could not create msmtp config: {e}")
    
    print("Setup complete!")
    print("Make sure to update EMAIL_USER and EMAIL_PASS in this script")
    print("Test with: python3 sms_email_bridge.py test")

# =============================================================================
# TEST
# =============================================================================
def test():
    """Test the email bridge"""
    print("Testing email bridge...")
    success = send_sms_to_email("+1234567890", "Test Contact", "This is a test message")
    if success:
        print("Test email sent successfully!")
    else:
        print("Test failed!")

# =============================================================================
# MAIN
# =============================================================================
def main():
    if len(sys.argv) < 2:
        print("SMS Email Bridge")
        print("Usage:")
        print("  python3 sms_email_bridge.py setup              - Initial setup")
        print("  python3 sms_email_bridge.py send PHONE NAME MSG - Forward SMS to email")
        print("  python3 sms_email_bridge.py check [quiet]      - Check for email replies")
        print("  python3 sms_email_bridge.py tasker             - Check emails (clean output for Tasker)")
        print("  python3 sms_email_bridge.py debug [all]        - Debug email parsing")
        print("  python3 sms_email_bridge.py test               - Test configuration")
        return
    
    command = sys.argv[1]
    
    if command == "setup":
        setup()
    
    elif command == "send":
        if len(sys.argv) < 5:
            print("Usage: python3 sms_email_bridge.py send PHONE NAME MESSAGE")
            return
        phone = sys.argv[2]
        name = sys.argv[3]
        message = " ".join(sys.argv[4:])
        send_sms_to_email(phone, name, message)
    
    elif command == "check":
        quiet = len(sys.argv) > 2 and sys.argv[2] == "quiet"
        check_email_replies(quiet_mode=quiet)
    
    elif command == "tasker":
        # Clean output mode for Tasker
        check_email_replies(quiet_mode=True)
    
    elif command == "debug":
        search_all = len(sys.argv) > 2 and sys.argv[2] == "all"
        debug_email(search_all=search_all)
    
    elif command == "test":
        test()
    
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()
