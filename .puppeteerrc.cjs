const {join} = require('path');

/**
 * @type {import("puppeteer").Configuration}
 */
module.exports = {
  // Download Chromium during installation
  skipDownload: false,

  // Use the bundled Chromium instead of system Chrome
  executablePath: undefined,

  // Cache directory for Puppeteer
  cacheDirectory: join(__dirname, '.cache', 'puppeteer'),
};
