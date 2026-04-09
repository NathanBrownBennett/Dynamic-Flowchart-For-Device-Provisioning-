const { test, expect } = require('@playwright/test');

test.describe('Device Provisioning Toolkit - intended behavior', () => {
  test('home page renders key intent sections', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /Device Provisioning Toolkit/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Find Your Device/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Secure Recommended Devices/i })).toBeVisible();
  });

  test('device search flow returns security-verified results', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Find Your Device/i }).click();

    await page.locator('#searchBar').fill('Mac');
    await page.locator('#use').selectOption('Work');
    await page.locator('#device_type').selectOption('Laptops');

    await page.getByRole('button', { name: /Find Secure Devices/i }).click();

    await expect(page.getByRole('heading', { name: /Security-Verified Search Results/i })).toBeVisible();
    await expect(page.locator('.device-card-result').first()).toBeVisible();
    await expect(page.locator('.security-badge').first()).toContainText(/Excellent|Good|Adequate|Risky/);
  });

  test('device details page provides security guidance and hardening script options', async ({ page }) => {
    await page.goto('/device/1');

    await expect(page.locator('.display-4')).toBeVisible();
    await page.locator('#security-tab').click();
    await expect(page.getByRole('heading', { name: /Complete Security Setup Guide/i })).toBeVisible();

    await expect(page.getByRole('heading', { name: /Automated Hardening Script/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Download Script/i })).toBeVisible();
  });

  test('compare tab can run comparison request and render a stable outcome', async ({ page }) => {
    await page.goto('/device/1');
    await page.locator('#compare-tab').click();

    await page.getByRole('button', { name: /Find Alternatives/i }).click();

    const noResults = page.getByText(/No comparable devices found/i);
    const cards = page.locator('.comparison-card');

    await expect
      .poll(async () => {
        const noResultsVisible = await noResults.count();
        const cardCount = await cards.count();
        return noResultsVisible > 0 || cardCount > 0;
      })
      .toBeTruthy();
  });

  test('async refresh endpoint is available from UI-triggered API', async ({ request }) => {
    const res = await request.post('/async-refresh');
    expect(res.status()).toBe(202);
    const json = await res.json();
    expect(['started', 'in_progress']).toContain(json.status);
  });

  test('404 routes return safe custom UX page', async ({ page }) => {
    const resp = await page.goto('/this-route-should-not-exist');
    expect(resp && resp.status()).toBe(404);

    await expect(page.getByRole('heading', { name: /404: Page Not Found/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /Back To Home/i })).toBeVisible();
  });

  test('advanced operating system filter currently does not constrain results (intent gap)', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Find Your Device/i }).click();

    await page.locator('#searchBar').fill('Mac');
    await page.locator('#operating_system').selectOption('Windows');
    await page.locator('#device_type').selectOption('Laptops');
    await page.getByRole('button', { name: /Find Secure Devices/i }).click();

    await expect(page.getByRole('heading', { name: /Security-Verified Search Results/i })).toBeVisible();

    // If OS filtering was honored, a Mac query + Windows filter should typically be empty.
    // Presence of a result here highlights a functionality gap relative to UI intent.
    await expect(page.locator('.device-card-result').first()).toBeVisible();
  });
});
