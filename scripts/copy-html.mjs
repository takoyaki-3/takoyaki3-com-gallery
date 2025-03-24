import * as dotenv from 'dotenv';
dotenv.config();
import fs from 'fs';
import path from 'path';

// Define paths
const sourcePath = path.resolve('public/index.html');
const destDir = path.resolve('dist');
const destPath = path.join(destDir, 'index.html');

/**
 * This script replaces placeholders in index.html with environment variables from GitHub Actions
 * Example variables from CDK deploy:
 * API_ENDPOINT: ${{ needs.deploy-aws.outputs.API_ENDPOINT }}
 * BUCKET_NAME: ${{ needs.deploy-aws.outputs.BUCKET_NAME }}
 *
 * In index.html, use: <api-endpoint>${API_ENDPOINT}</api-endpoint>
 */

// Create 'dist' directory if it doesn't exist
if (!fs.existsSync(destDir)) {
  fs.mkdirSync(destDir, { recursive: true });
}

// Read the source file
fs.readFile(sourcePath, 'utf8', (err, data) => {
  if (err) {
    console.error('Error reading the file:', err);
    return;
  }

  // Keep track of missing variables
  const missingVars = [];

  // Replace placeholders with environment variables
  const modifiedData = data.replace(/\${(.*?)}/g, (match, variableName) => {
    if (!process.env[variableName]) {
      missingVars.push(variableName);
      return match; // Keep original if env var is not found
    }
    return process.env[variableName];
  });

  // Warn about missing variables
  if (missingVars.length > 0) {
    console.warn('⚠️ Warning: The following environment variables were not found in .env file:');
    missingVars.forEach(varName => console.warn(`  - ${varName}`));
    console.warn('Please make sure to define them in your .env file.');
  }

  // Write the modified content to the destination file
  fs.writeFile(destPath, modifiedData, 'utf8', (err) => {
    if (err) {
      console.error('Error writing to the file:', err);
      return;
    }
    console.log('✅ File copied and environment variables replaced successfully!');
  });
});