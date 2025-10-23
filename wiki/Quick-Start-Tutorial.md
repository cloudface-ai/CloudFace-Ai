# ⚡ Quick Start Tutorial

Get **CloudFace AI** up and running in under 10 minutes! This tutorial will walk you through the essential steps to start using the application.

## 🎯 What You'll Learn

- Start the application
- Upload and process your first photos
- Search for faces in your collection
- Basic navigation and features

## 🚀 Step 1: Start the Application

### **Option A: Web Application (Recommended for beginners)**
```bash
# Navigate to your project directory
cd cloudface-ai.com

# Start the web server
python web_server.py
```

**Open your browser and go to:** `http://localhost:8550`

### **Option B: Desktop Application**
```bash
# Start the desktop app
python main_app.py
```

## 🔐 Step 2: Sign In

1. **Click "Sign in with Google"** on the landing page
2. **Complete Google OAuth** authentication
3. **Grant necessary permissions** when prompted
4. **You'll be redirected back** to the main application

## 📸 Step 3: Upload Your First Photos

### **Using the Web Interface**

1. **Navigate to the main app** (`/app` route)
2. **Click "Upload Photos"** or drag & drop images
3. **Select multiple photos** from your computer
4. **Click "Process Photos"** to start face detection

### **Using the Desktop App**

1. **Click "Select Photos"** button
2. **Choose a folder** containing your photos
3. **Click "Process Folder"** to begin

## 🔍 Step 4: Process Photos

The system will automatically:

1. **Detect faces** in each uploaded photo
2. **Generate face embeddings** (AI fingerprints)
3. **Store data** in your Supabase database
4. **Show progress** with real-time updates

**Processing time depends on:**
- Number of photos
- Photo resolution
- Number of faces per photo
- Your computer's performance

## 🎯 Step 5: Search for Faces

### **Upload a Selfie**
1. **Click "Upload Selfie"** or use your camera
2. **Take or select** a photo with a clear face
3. **Click "Find Similar Faces"**

### **View Results**
The system will show:
- **Similarity score** for each match
- **Thumbnail previews** of matching photos
- **Distance metrics** (lower = more similar)
- **Photo references** for easy identification

## ⚙️ Step 6: Adjust Search Settings

### **Similarity Thresholds**
- **Strict (0.4)**: Very similar faces only
- **Standard (0.6)**: Similar faces (recommended)
- **Loose (0.8)**: Somewhat similar faces

### **Search Filters**
- **Date range**: Search within specific time periods
- **Photo source**: Filter by upload source
- **Face count**: Photos with specific number of faces

## 📊 Step 7: Explore Your Collection

### **Browse Photos**
- **View all processed photos** in your collection
- **Organize by date** or similarity
- **Filter by face count** or tags

### **Face Groups**
- **Automatic grouping** of similar faces
- **Manual organization** options
- **Export capabilities** for analysis

## 🔧 Step 8: Customize Your Experience

### **Profile Settings**
- **Update profile information**
- **Adjust privacy settings**
- **Manage connected accounts**

### **Application Preferences**
- **Default search thresholds**
- **Interface themes**
- **Notification settings**

## 📱 Step 9: Use on Different Devices

### **Web Access**
- **Access from any device** with a web browser
- **Responsive design** for mobile and desktop
- **Cross-platform compatibility**

### **Desktop App**
- **Native performance** on your computer
- **Offline capabilities** for local processing
- **System integration** features

## 🚨 Common Quick Start Issues

### **Photos Not Processing**
- Check if faces are clearly visible
- Ensure photos are in supported formats (JPG, PNG, JPEG)
- Verify internet connection for database access

### **No Search Results**
- Lower the similarity threshold
- Ensure your selfie has a clear, front-facing face
- Check if photos were processed successfully

### **Authentication Problems**
- Clear browser cookies and cache
- Check Google OAuth credentials in `.env`
- Verify redirect URIs in Google Cloud Console

## 🎉 Congratulations!

You've successfully:
- ✅ Started CloudFace AI
- ✅ Authenticated with Google
- ✅ Processed your first photos
- ✅ Searched for similar faces
- ✅ Explored the basic features

## 🚀 Next Steps

Now that you're up and running:

1. **Read the [Web Application Guide](Web-Application-Guide.md)** for advanced features
2. **Explore [Photo Processing Guide](Photo-Processing-Guide.md)** for optimization tips
3. **Check [Configuration](Configuration.md)** for customization options
4. **Visit [Troubleshooting](Troubleshooting.md)** if you need help

## 💡 Pro Tips

- **Start with a small photo collection** to test the system
- **Use clear, well-lit photos** for better face detection
- **Experiment with different thresholds** to find your optimal setting
- **Process photos in batches** for better performance
- **Regular backups** of your face embeddings

---

**Ready to explore more?** Dive into the [Web Application Guide](Web-Application-Guide.md) to unlock all the advanced features!
