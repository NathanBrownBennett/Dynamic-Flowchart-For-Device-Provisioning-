const { test, expect } = require('@playwright/test');

test.describe('Device Provisioning Toolkit - interactive pilot', () => {
  test('home page explains the decision workflow', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /Find a device that fits/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Browse devices/i })).toHaveClass(/active/);
    await expect(page.getByRole('heading', { name: /Tell us what you need/i })).toBeVisible();
  });

  test('primary navigation switches views without a long page scroll', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /How scoring works/i }).click();
    await expect(page.getByRole('heading', { name: /Simple decisions, clearly explained/i })).toBeVisible();
    await expect(page).toHaveURL(/#guide/);
    await page.getByRole('button', { name: /Browse devices/i }).click();
    await expect(page.getByRole('heading', { name: /Tell us what you need/i })).toBeVisible();
    await expect(page).toHaveURL(/#browse/);
  });

  test('domestic search returns reviewed recommendations', async ({ page }) => {
    await page.goto('/');
    await page.getByLabel('What matters most?').selectOption('security');
    await page.getByRole('button', { name: /Show recommendations/i }).click();

    await expect(page.getByRole('heading', { name: /Current catalogue/i })).toBeVisible();
    await expect(page.locator('.device-card').first()).toBeVisible();
    await expect(page.locator('.score').first()).toContainText('%');
  });

  test('business role context reaches device review', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Small business/i }).click();
    await page.getByLabel('Work role').selectOption('privileged_admin');
    await page.getByRole('button', { name: /Show recommendations/i }).click();
    await page.locator('.device-card').first().getByRole('button', { name: /Review device/i }).click();

    await expect(page.getByText(/Recommendation for: Business · privileged admin/i)).toBeVisible();
    await expect(page.getByRole('heading', { name: /Evidence and limits/i })).toBeVisible();
    await page.getByRole('tab', { name: /Security/i }).click();
    await expect(page.getByRole('heading', { name: /Security score breakdown/i })).toBeVisible();
    await page.getByRole('tab', { name: /Vendors/i }).click();
    await expect(page.getByRole('heading', { name: /Where to buy|Vendor offers/i })).toBeVisible();
    const download = page.waitForEvent('download');
    await page.getByRole('button', { name: /Download summary/i }).click();
    await expect((await download).suggestedFilename()).toMatch(/device-decision-\d+\.txt/);
  });

  test('government context is retained in review and alternatives', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Public sector/i }).click();
    await page.getByRole('button', { name: /Show recommendations/i }).click();
    await page.locator('.device-card').first().getByRole('button', { name: /Review device/i }).click();

    await expect(page.getByText(/Recommendation for: Government/i)).toBeVisible();
    await page.getByRole('button', { name: /Find alternatives/i }).click();
    await expect(page.getByRole('heading', { name: /Similar choices/i })).toBeVisible();
  });

  test('filters are reflected in the URL', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Small business/i }).click();
    await page.getByLabel('Maximum price (£)').fill('1500');
    await page.getByRole('button', { name: /Show recommendations/i }).click();
    await expect(page).toHaveURL(/use_case=Work/);
    await expect(page).toHaveURL(/price_max=1500/);
  });

  test('operator refresh remains unavailable to public users', async ({ request }) => {
    const res = await request.post('/async-refresh');
    expect(res.status()).toBe(503);
    const json = await res.json();
    expect(json.error).toBe('operator action is disabled');
  });

  test('public pilot wording is visible in the application footer', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('footer').getByText(/public pilot/i)).toBeVisible();
    await expect(page.getByText(/no account, sign-up or personal data/i)).toBeVisible();
  });
});
