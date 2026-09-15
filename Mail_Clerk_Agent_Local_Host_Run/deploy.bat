@echo off
echo Building deployment package for AWS Lambda...

:: Step 1: Remove old package directory if exists
if exist package rmdir /s /q package
if exist deployment_package.zip del deployment_package.zip

:: Step 2: Install dependencies into package folder
pip install --target ./package -r requirements.txt

:: Step 3: Copy source files into package folder
cd package
powershell Compress-Archive -Path * -DestinationPath ..\deployment_package.zip -Force
cd ..

:: Step 4: Add application code to zip file
powershell Compress-Archive -Path config.py, email_service.py, ai_classifier.py, audit_logger.py, agent.py, lambda_handler.py, institutes.json -Update -DestinationPath deployment_package.zip

echo Deployment package created: deployment_package.zip