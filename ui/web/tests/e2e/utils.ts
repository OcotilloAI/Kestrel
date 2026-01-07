import { Page, expect } from '@playwright/test';

/**
 * Ensures the sidebar is visible.
 * On desktop viewports, the sidebar is already visible by default.
 * On mobile viewports, a toggle button needs to be clicked.
 */
export async function ensureSidebarVisible(page: Page): Promise<void> {
  const sidebar = page.getByTestId('sidebar');

  // Check if sidebar is already visible
  const isVisible = await sidebar.isVisible().catch(() => false);
  if (isVisible) {
    return;
  }

  // Try to find and click the toggle button (mobile/collapsed view)
  const toggle = page.locator('[aria-label="Toggle sidebar"], .mobile-menu-btn');
  const toggleCount = await toggle.count();
  if (toggleCount > 0) {
    await toggle.first().click();
    await expect(sidebar).toBeVisible();
  }
}

/**
 * Handles login if the password prompt is visible.
 */
export async function handleLogin(page: Page, password = 'k3str3lrocks'): Promise<void> {
  const passwordInput = page.getByPlaceholder('Password');
  if (await passwordInput.count()) {
    await passwordInput.fill(password);
    await page.getByRole('button', { name: 'Login' }).click();
    await page.waitForTimeout(1000);
  }
}

/**
 * Ensures a project exists, creating one if needed.
 */
export async function ensureProjectExists(page: Page): Promise<void> {
  const projectSelect = page.getByTestId('project-select');
  const projectOptions = await projectSelect.locator('option').allTextContents();
  if (projectOptions.length === 0) {
    await page.getByTestId('project-create-button').click();
    await page.waitForTimeout(1200);
  }
}
