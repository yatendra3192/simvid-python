@echo off
echo ========================================
echo Push SimVid Python to GitHub
echo ========================================
echo.
echo Please make sure you have:
echo 1. Created a new repository on GitHub.com called "simvid-python"
echo 2. Copied your repository URL (https://github.com/YOUR_USERNAME/simvid-python.git)
echo.
set /p repo_url="Enter your GitHub repository URL: "
echo.
echo Adding remote origin...
git remote add origin %repo_url%
echo.
echo Renaming branch to main...
git branch -M main
echo.
echo Pushing to GitHub...
git push -u origin main
echo.
echo ========================================
echo Successfully pushed to GitHub!
echo Your repository is now available at: %repo_url%
echo.
echo Next steps:
echo 1. Go to Railway.app
echo 2. Create new project from GitHub repo
echo 3. Select your simvid-python repository
echo ========================================
pause