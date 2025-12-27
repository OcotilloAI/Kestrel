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

  await expect(page.getByTestId('project-select')).toBeVisible();

  const projectSelect = page.getByTestId('project-select');
  const projectOptions = await projectSelect.locator('option').allTextContents();
  expect(projectOptions.length).toBeGreaterThan(0);

  await page.getByTestId('branch-name-input').fill(branchName);
  await page.getByTestId('branch-create-button').click();

  const branchItem = page.getByTestId(`branch-item-${branchName}`);
  await expect(branchItem).toBeVisible();

  await page.getByTestId(`branch-delete-${branchName}`).click();
  await expect(page.getByTestId('confirm-modal')).toBeVisible();
  await page.getByTestId('confirm-delete').click();
  await expect(branchItem).toBeHidden();
});
