const puppeteer = require('puppeteer');

(async () => {
    console.log('🎭 Testing Puppeteer image loading...');

    const browser = await puppeteer.launch({
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process'
        ]
    });

    const page = await browser.newPage();

    // Test URL with Wix images
    const testUrl = 'https://bsl-utilidades-yp78a.ondigitalocean.app/preview-certificado-html/4bc7fcab-1d29-4e14-bcf6-fb46819d6c04';

    console.log(`🌐 Loading: ${testUrl}`);

    await page.goto(testUrl, {
        waitUntil: ['load', 'networkidle0'],
        timeout: 45000
    });

    console.log('✅ Page loaded');

    // Check images
    const imageInfo = await page.evaluate(() => {
        const images = Array.from(document.images);
        return images.map(img => ({
            src: img.src.substring(0, 100),
            complete: img.complete,
            naturalWidth: img.naturalWidth,
            naturalHeight: img.naturalHeight
        }));
    });

    console.log('🖼️  Images found:', imageInfo.length);
    imageInfo.forEach((img, i) => {
        console.log(`  ${i + 1}. ${img.complete ? '✅' : '❌'} ${img.src}... (${img.naturalWidth}x${img.naturalHeight})`);
    });

    // Generate PDF
    await page.pdf({
        path: '/tmp/test-puppeteer.pdf',
        format: 'Letter',
        printBackground: true,
        margin: {
            top: '0.5cm',
            right: '0.5cm',
            bottom: '0.5cm',
            left: '0.5cm'
        }
    });

    console.log('📄 PDF generated at /tmp/test-puppeteer.pdf');

    await browser.close();
    console.log('✅ Done');
})();
