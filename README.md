# SMS Email Bridge

A Python script that creates a bidirectional bridge between SMS messages and email. Very much a hacked together proof of concept.

## Motivation

1. Typing on some phones, such as the Light Phone III, is a less-than-stellar experience. I'd much rather type on a physical keyboard.
2. I no longer want to carry my phone with me day-to-day, but I acknowledge that an urgent message could (but probably won't) come through during my eight hours at the office. The Light Phone II & III both support forwarding MMS messages, and messages with links to your email, but that's as far as that goes. I want to take things a step further by forwarding all messages, and be able to reply to them from my email.

## Features

- **📧 SMS to Email**: Automatically forward incoming SMS messages to your email
- **📱 Email to SMS**: Reply to SMS messages by replying to the email

## How It Works

1. **Incoming SMS** → Tasker detects → Script forwards to email
2. **Email Reply** → Script monitors inbox → Sends SMS to original sender
3. **Repeat** → Full conversation flows between SMS and email seamlessly

## Requirements

### Android Device

- **Termux** - Terminal emulator for Android
- **Tasker** - Android automation app
- Android device with SMS capabilities

## Setup

TODO
