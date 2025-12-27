import { test, expect } from '@playwright/test';

test('create and delete a branch from the sidebar', async ({ page }) => {
  const branchName = `pw-branch-${Date.now().toString().slice(-6)}`;

  await page.goto('/');

  const password = page.getByPlaceholder('Password');
  if (await password.count()) {
    await password.fill('k3str3lrocks');
    await page.getByRole('button', { name: 'Login' }).click();
  }

  const toggle = page.locator('[aria-label="Toggle sidebar"], .mobile-menu-btn');
  await expect(toggle.first()).toBeVisible();
  await toggle.first().click();

  await expect(page.getByText('Current Project')).toBeVisible();

  const projectSelect = page.locator('label:has-text("Current Project")').locator('..').locator('select');
  const projectOptions = await projectSelect.locator('option').allTextContents();
  expect(projectOptions.length).toBeGreaterThan(0);

  await page.getByPlaceholder('New branch name (optional)').fill(branchName);
  await page.getByRole('button', { name: 'Create Branch' }).click();

  const branchItem = page.locator('.list-group-item').filter({ hasText: branchName }).first();
  await expect(branchItem).toBeVisible();

  await branchItem.locator('button[title="Delete Branch"]').click();
  const dialog = page.getByRole('dialog').filter({ hasText: 'Delete Branch' });
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: 'Delete' }).click();
  await expect(branchItem).toBeHidden();
});
