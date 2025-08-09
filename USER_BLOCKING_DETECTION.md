# User Blocking/Unblocking Detection Documentation

## Overview
Your `get_chat.py` file now correctly tracks when individual users block or unblock your bot in private chats, updating the `BotUser.is_active` field accordingly.

## Key Changes Made

### 🎯 **Focus on Private Chats**
- **Before**: Tracked channel/group membership changes
- **After**: Tracks user blocking/unblocking in private chats
- **Target**: `BotUser` table, not `BotChat` table

### 🔄 **How It Works**

#### When User Blocks Bot:
```
User blocks bot → my_chat_member_handler() → BotUser.is_active = False
```

#### When User Unblocks Bot:
```
User unblocks bot → my_chat_member_handler() → BotUser.is_active = True
```

### 📱 **Detection Logic**

#### Private Chat Detection:
```python
if chat.type == "private":
    # Handle user blocking/unblocking
```

#### Status Change Detection:
```python
# User blocked bot
if new_status in ["kicked", "left"] and old_status == "member":
    await db.update_user_active_status(user_id=user.id, is_active=False)

# User unblocked bot  
elif new_status == "member" and old_status in ["kicked", "left"]:
    await db.update_user_active_status(user_id=user.id, is_active=True)
```

## Database Implementation

### New Function Added:
```python
async def update_user_active_status(user_id: int, is_active: bool):
    """Update user active status in BotUser table"""
    user = BotUser.objects.get(user_id=user_id)
    user.is_active = is_active
    user.save()
```

### What Gets Updated:
- **Table**: `BotUser` (not `BotChat`)
- **Field**: `is_active` (True/False)
- **Target**: Individual users who block/unblock bot

## Event Flow

### 📱 **User Blocks Bot**
1. User goes to bot chat and blocks it
2. Telegram sends `my_chat_member_handler` update
3. `old_status: "member"` → `new_status: "kicked"`
4. Bot detects private chat blocking
5. Database: `BotUser.is_active = False`
6. Log: "User X blocked the bot - set is_active=False"

### ✅ **User Unblocks Bot**
1. User unblocks bot in private chat
2. Telegram sends `my_chat_member_handler` update  
3. `old_status: "kicked"` → `new_status: "member"`
4. Bot detects private chat unblocking
5. Database: `BotUser.is_active = True`
6. Log: "User X unblocked the bot - set is_active=True"

### 🏢 **Channel/Group Events (Unchanged)**
- Bot added to channel → Creates `BotChat` record
- Bot removed from channel → Deactivates `BotChat`
- Bot gets admin rights → Updates `BotChat.is_admin`

## Benefits

### 🎯 **Accurate User Tracking**
- Know exactly which users have blocked your bot
- Track user engagement at individual level
- Identify inactive vs blocked users

### 📊 **Better Analytics**
```python
# Query examples:
active_users = BotUser.objects.filter(is_active=True).count()
blocked_users = BotUser.objects.filter(is_active=False).count()
total_users = BotUser.objects.count()
```

### 🚀 **Improved Bot Management**
- Don't send messages to users who blocked the bot
- Focus marketing efforts on active users
- Monitor user retention patterns

## Logging and Monitoring

### What Gets Logged:
- User blocking events with user ID and username
- User unblocking events with user ID and username
- Database update success/failure
- Error handling for edge cases

### Optional Admin Notifications:
```python
# Uncomment to enable notifications
await bot.send_message(
    chat_id=1376269802,
    text=f"🚫 User blocked bot: {user.first_name} (@{user.username})"
)
```

## Use Cases

### 🎯 **Message Broadcasting**
```python
# Only send to active users
active_users = await db.get_active_users()
for user in active_users:
    if user.is_active:  # Skip blocked users
        await bot.send_message(user.user_id, message)
```

### 📊 **User Analytics**
```python
# Dashboard metrics
total_users = BotUser.objects.count()
active_users = BotUser.objects.filter(is_active=True).count()
blocked_rate = ((total_users - active_users) / total_users) * 100
```

### 🔄 **Re-engagement Campaigns**
```python
# Target users who recently became inactive
recently_inactive = BotUser.objects.filter(
    is_active=False,
    updated_at__gte=yesterday
)
```

## Error Handling

### Database Errors:
- Graceful handling when user doesn't exist in database
- Continued operation even if database update fails
- Comprehensive error logging

### Edge Cases:
- User deletes and recreates Telegram account
- Bot restart during status change events
- Network issues during database updates

## Files Modified

1. **`bot/handlers/users/get_chat.py`**
   - Added private chat detection for user blocking/unblocking
   - Maintained existing channel/group functionality
   - Enhanced logging and error handling

2. **`bot/utils/db_api/db.py`**
   - Added `update_user_active_status()` function
   - Targets `BotUser` table specifically
   - Lightweight update operation

Your bot now accurately tracks individual user blocking/unblocking behavior, giving you precise insights into user engagement!
