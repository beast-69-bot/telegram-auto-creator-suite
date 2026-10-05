# 🚀 Telegram Auto Creator Suite

Telegram पर **Bots (@BotFather)** और **Public Channels** ऑटोमैटिक क्रिएट करने का पूरा ऑटोमेशन टूल।

## 🌟 मुख्य फीचर्स (Features):
1. **Multi-Account Login:**
   * आप जितने चाहें Telegram Accounts `/login` कमांड से कनेक्ट कर सकते हैं।
   * Sessions डेटाबेस में सुरक्षित सेव रहते हैं।
2. **Smart Shuffle / Round-Robin:**
   * अगर आपने 3 अकाउंट्स कनेक्ट किए हैं और 30 बॉट्स बनाने का टास्क दिया, तो हर अकाउंट से बारी-बारी (Account 1 -> Account 2 -> Account 3...) बॉट बनेंगे। इससे टेलीग्राम रेट-लिमिट/स्पैम डिटेक्ट नहीं करता।
3. **Auto-Fade Quota Limit:**
   * जब किसी अकाउंट का कोटा फुल हो जाता है (20 Bots या 10 Public Channels, या BotFather से limit एरर आता है), बॉट उस अकाउंट को ऑटोमैटिक **Fade / Inactive** कर देता है और बाकी बचे अकाउंट्स पर स्विच हो जाता है।
4. **Random Unique Names & Usernames:**
   * आप जो Base Name/Username देंगे (जैसे `Viral Saver` -> `viral_saver`), बॉट उससे मिलते-जुलते यूनिक यूजरनेम खुद जनरेट करता है। अगर कोई यूजरनेम पहले से लिया हुआ हो, तो ऑटोमैटिक अगला वेरिएशन ट्राई करता है।
5. **Configurable Qty & Time Interval:**
   * कितने बॉट/चैनल बनाने हैं (`qty`) और कितने सेकंड का गैप (`interval`) रखना है, यह आप तय करते हैं।
6. **Token & Link Delivery:**
   * हर बॉट/चैनल बनने पर लाइव मैसेज मिलता है।
   * पूरा टास्क खत्म होने पर **पूरी समरी फाइल (.txt)** एडमिन को भेजी जाती है जिसमें सारे बॉट्स के Tokens, Usernames और चैनल्स के Links होते हैं।

---

## ⚙️ Setup & Configuration:

### 1. `.env` फाइल बनाएं:
प्रोजेक्ट डायरेक्टरी में `.env` फाइल बनाएं (या `auto_creator/.env.example` को कॉपी करके `.env` नाम दें):

```env
API_ID=12345678
API_HASH=your_api_hash_here
BOT_TOKEN=your_controller_bot_token_here
ADMIN_IDS=your_telegram_user_id
```
* **API_ID & API_HASH:** [my.telegram.org](https://my.telegram.org) से लें।
* **BOT_TOKEN:** [@BotFather](https://t.me/BotFather) से अपने कंट्रोलर बॉट के लिए लें।
* **ADMIN_IDS:** आपकी अपनी Telegram User ID (ताकि सिर्फ आप ही इसे चला सकें)।

### 2. बॉट रन करें:
```bash
python run_auto_creator.py
```

---

## 📱 Bot Commands:

| Command | विवरण |
| :--- | :--- |
| `/start` | मुख्य मेनू और बटन्स दिखाता है |
| `/login` | नया टेलीग्राम अकाउंट इंटरएक्टिवली लॉग-इन करें (Phone -> OTP -> 2FA) |
| `/accounts` | सभी कनेक्टेड अकाउंट्स, उनका स्टेटस (Active/Fade) और कोटा देखें |
| `/createbot` | बॉट्स क्रिएशन विज़ार्ड (Name, Username, Description, About, Photo, Qty, Interval) |
| `/createchannel` | पब्लिक चैनल क्रिएशन विज़ार्ड (Title, Username, Description, Photo, Qty, Interval) |
| `/status` | अभी चल रहे लाइव टास्क्स की प्रोग्रेस देखें |
| `/cancel` | कोई भी चालू विज़ार्ड या टास्क कैंसिल करें |
