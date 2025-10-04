# Aiezzy Simvid 🎬

A web-based slideshow video generator that creates MP4 videos from your images with background music. Upload images, add YouTube audio or your own music, and generate beautiful slideshow videos instantly!

## 🌟 Features

- **Drag & Drop Image Upload** - Simply drag your images or click to browse
- **YouTube Audio Download** - Add background music from any YouTube video
- **Custom Audio Upload** - Upload your own MP3/WAV files
- **Multiple Resolutions** - Support for various video formats (720p, 1080p, etc.)
- **Real-time Preview** - See your images before generating the video
- **Mobile Friendly** - Works on phones and tablets with screen sleep prevention
- **No Installation Required** - Access via web browser

## 🚀 Live Demo

Try it now: [https://aiezzy-simvid.up.railway.app](https://aiezzy-simvid.up.railway.app)

## 🛠️ Technology Stack

- **Backend**: Python Flask
- **Frontend**: HTML5, JavaScript, CSS
- **Video Processing**: MoviePy
- **Audio Download**: yt-dlp
- **Deployment**: Railway

## 📋 Requirements

For local development:
- Python 3.8+
- pip (Python package manager)
- FFmpeg (optional, for advanced features)

## 🔧 Installation

1. Clone the repository:
```bash
git clone https://github.com/yatendra3192/simvid-python.git
cd simvid-python
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

4. Open your browser and visit:
```
http://localhost:5000
```

## 📖 How to Use

1. **Upload Images**
   - Drag and drop images onto the upload area
   - Or click "Select Images" to browse files
   - Supported formats: JPG, PNG, GIF, BMP, WebP

2. **Add Background Music (Optional)**
   - **Option 1**: Paste a YouTube URL and click "Download Audio"
   - **Option 2**: Upload your own audio file (MP3, WAV, M4A)

3. **Configure Settings**
   - **Duration**: Set how long each image displays (1-10 seconds)
   - **Transition**: Choose transition effect (currently fade)
   - **Resolution**: Select video quality

4. **Generate Video**
   - Click "Generate Video" button
   - Wait for processing (larger videos take longer)
   - Download your video when complete

## 🐛 Known Issues

- Video generation with audio is currently being fixed
- Large file uploads may timeout on free hosting
- Some mobile browsers may have upload limitations

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is open source and available under the MIT License.

## 🙏 Acknowledgments

- MoviePy for video processing
- yt-dlp for YouTube downloads
- Flask for the web framework
- Railway for hosting

## 📞 Support

For issues and questions, please [open an issue](https://github.com/yatendra3192/simvid-python/issues) on GitHub.

## 🚧 Development Status

This project is actively under development. Features are being added and bugs are being fixed regularly. Check back for updates!

---

**Made with ❤️ by Yatendra**