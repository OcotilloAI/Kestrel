import { test, expect } from '@playwright/test';

test('merge branch into main from sidebar', async ({ page }) => {
  const branchName = `pw-branch-${Date.now().toString().slice(-6)}`;

  await page.goto('/');
  const password = page.getByPlaceholder('Password');
  if (await password.count()) {
    await password.fill('k3str3lrocks');
    await page.getByRole('button', { name: 'Login' }).click();
    await page.waitForTimeout(1000);
  }

  const toggle = page.locator('[aria-label="Toggle sidebar"], .mobile-menu-btn');
  await expect(toggle.first()).toBeVisible();
  await toggle.first().click();

  await expect(page.getByTestId('project-select')).toBeVisible();
  const projectOptions = await page.getByTestId('project-select').locator('option').allTextContents();
  if (projectOptions.length === 0) {
    await page.getByTestId('project-create-button').click();
    await page.waitForTimeout(1200);
  }

  await page.getByTestId('branch-name-input').fill(branchName);
  await page.getByTestId('branch-create-main-button').click();

  const branchItem = page.getByTestId(`branch-item-${branchName}`);
  await expect(branchItem).toBeVisible();

  await page.getByTestId(`branch-merge-${branchName}`).click();
  await expect(page.getByTestId('confirm-modal')).toBeVisible();
  await page.getByTestId('confirm-delete').click();

  await expect(page.getByTestId(`branch-merge-${branchName}`)).toBeVisible();
});
