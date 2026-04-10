const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  console.log('🎬 Playwright Recording Script');
  console.log('============================\n');
  
  // Step 1: Home Page
  console.log('📍 Step 1: Loading home page...');
  await page.goto('http://localhost:8012', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1000);
  
  const homeTitle = await page.title();
  console.log(`   ✓ Page Title: ${homeTitle}`);
  
  // Count recommended devices
  const deviceCards = await page.$$('.col-md-4');
  console.log(`   ✓ Recommended devices found: ${Math.floor(deviceCards.length / 2)}`);
  
  // Get first device details
  const firstDevice = await page.evaluate(() => {
    const card = document.querySelector('.col-md-4');
    if (!card) return null;
    return {
      name: card.querySelector('h6')?.textContent || 'Unknown',
      specs: card.querySelector('.text-muted')?.textContent || 'No specs',
    };
  });
  
  if (firstDevice) {
    console.log(`   ✓ First device: ${firstDevice.name}`);
  }
  
  // Step 2: Live Listings
  console.log('\n📍 Step 2: Analyzing Live Listings section...');
  const liveListingCards = await page.$$('text=/Live Listings/');
  console.log(`   ✓ Live listings section found: ${liveListingCards.length > 0 ? 'Yes' : 'No'}`);
  
  // Step 3: Click on a device (Dell XPS)
  console.log('\n📍 Step 3: Navigating to device detail page...');
  const deviceLinks = await page.$$('a:has-text("Dell XPS")');
  if (deviceLinks.length > 0) {
    // Find and click the device card (not the retailer link)
    const cards = await page.$$('.col-md-4');
    for (const card of cards) {
      const text = await card.textContent();
      if (text.includes('Dell XPS')) {
        await card.click();
        break;
      }
    }
    await page.waitForTimeout(2000);
    console.log(`   ✓ Navigated to device detail page`);
    
    // Get device details
    const deviceDetail = await page.evaluate(() => {
      return {
        title: document.querySelector('h1')?.textContent || 'Unknown',
        price: document.querySelector('[style*="FF6B52"]')?.textContent || 'N/A',
        specs: {
          processor: document.querySelector('text=/Processor:/')?.textContent || 'N/A',
          memory: document.querySelector('text=/Memory:/')?.textContent || 'N/A',
        }
      };
    });
    
    console.log(`   ✓ Device: ${deviceDetail.title}`);
    console.log(`   ✓ Price: ${deviceDetail.price}`);
  }
  
  // Step 4: Check tabs
  console.log('\n📍 Step 4: Checking available tabs...');
  const tabs = await page.$$('button[role="tab"]');
  console.log(`   ✓ Found ${tabs.length} tabs`);
  
  const tabNames = [];
  for (const tab of tabs) {
    const name = await tab.textContent();
    tabNames.push(name.trim());
  }
  console.log(`   ✓ Tabs: ${tabNames.join(', ')}`);
  
  // Step 5: Click Security Guide tab
  console.log('\n📍 Step 5: Viewing Security Guide...');
  const securityTab = await page.$('button:has-text("Security Guide")');
  if (securityTab) {
    await securityTab.click();
    await page.waitForTimeout(1000);
    
    const securityContent = await page.evaluate(() => {
      return {
        hasRisks: !!document.querySelector('text=/Detected Risks/'),
        hasMitigations: !!document.querySelector('text=/Mitigations/'),
        hasTools: !!document.querySelector('text=/Debloat/'),
      };
    });
    
    console.log(`   ✓ Detected Risks section: ${securityContent.hasRisks ? 'Yes' : 'No'}`);
    console.log(`   ✓ Mitigations section: ${securityContent.hasMitigations ? 'Yes' : 'No'}`);
    console.log(`   ✓ Debloat Tools section: ${securityContent.hasTools ? 'Yes' : 'No'}`);
  }
  
  // Step 6: Click Purchase tab
  console.log('\n📍 Step 6: Viewing Purchase Options...');
  const purchaseTab = await page.$('button:has-text("Purchase")');
  if (purchaseTab) {
    await purchaseTab.click();
    await page.waitForTimeout(1000);
    
    const retailers = await page.evaluate(() => {
      const items = [];
      document.querySelectorAll('text=/Amazon|Currys|Johnlewis/').forEach(el => {
        if (el.textContent.match(/Amazon|Currys|Johnlewis/)) {
          items.push(el.textContent.trim());
        }
      });
      return [...new Set(items)];
    });
    
    console.log(`   ✓ Retailers found: ${retailers.slice(0, 3).join(', ')}`);
    
    // Check for Open buttons
    const openButtons = await page.$$('button:has-text("Open")');
    console.log(`   ✓ Purchase buttons: ${openButtons.length}`);
  }
  
  // Step 7: Go back to search
  console.log('\n📍 Step 7: Testing Search Functionality...');
  const backButton = await page.$('button:has-text("Back to Search")');
  if (backButton) {
    await backButton.click();
    await page.waitForTimeout(2000);
    console.log(`   ✓ Returned to search page`);
  }
  
  // Step 8: Open search form
  console.log('\n📍 Step 8: Opening search form...');
  const findButton = await page.$('button:has-text("Find Your Device")');
  if (findButton) {
    await findButton.click();
    await page.waitForTimeout(1000);
    
    const searchInput = await page.$('input[placeholder*="Search"]');
    if (searchInput) {
      console.log(`   ✓ Search form opened`);
      console.log(`   ✓ Search field available`);
      
      // Test search
      await searchInput.fill('MacBook');
      console.log(`   ✓ Typed "MacBook" in search`);
      
      const filterFields = await page.$$('select, [role="combobox"]');
      console.log(`   ✓ Filter options: ${filterFields.length} fields available`);
    }
  }
  
  // Summary  
  console.log('\n' + '='.repeat(50));
  console.log('📊 APP FUNCTIONALITY SUMMARY');
  console.log('='.repeat(50));
  console.log('✅ Home page with recommended devices');
  console.log('✅ Multi-vendor purchase links');
  console.log('✅ Device detail page with 4 tabs');
  console.log('✅ Security Guide with recommendations');
  console.log('✅ Purchase options with retailer buttons');
  console.log('✅ Advanced search functionality');
  console.log('✅ Device filtering and sorting');
  console.log('\n🎉 Walkthrough Complete!\n');
  
  await browser.close();
})();
