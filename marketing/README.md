# Odometer marketing site

A dependency-free static site for introducing Odometer and directing visitors to the GitHub repository. All fonts and assets are local; no analytics, cookies, or third-party scripts are loaded.

## Preview

From the repository root:

```sh
python3 -m http.server 8080 --directory marketing
```

Open http://localhost:8080. Opening `index.html` directly also works, though clipboard permissions depend on the browser; when copying is unavailable, the commands are selected for manual copying.

## Deploy

Publish the **contents of `marketing/`** to any static host. There is no build step. Asset URLs are relative, so hosting under `/odometer/` works. The dedicated workflow is [marketing-pages.yml](../.github/workflows/marketing-pages.yml). It uploads only `marketing/` as the artifact root, so `index.html` is served at the site root, not `/marketing/`. It has only a `workflow_dispatch` trigger: pushes and pull requests do not publish. No hosting is enabled by adding this file.

### GitHub Pages setup and manual publishing

These steps are for a repository maintainer **after separate deployment approval**. Preparing this workflow does not authorize pushing, merging, enabling hosting, or running it.

1. Review and obtain authorization to push/merge the scoped repository changes. The workflow must exist on the default branch for its **Run workflow** button to appear.
2. In **Settings → Pages → Build and deployment**, select **GitHub Actions** as the source. Ensure repository/organization Actions policy allows the official actions used in the workflow. Repository visibility and plan must support Pages.
3. In **Settings → Environments → github-pages**, configure required reviewers (where supported) and restrict deployment branches to the approved default branch. Keep the separate human deployment approval even if environment protection is unavailable. Do not enable Pages automatically through `configure-pages`.
4. After release approval, open **Actions → Publish Odometer marketing site → Run workflow**, select the approved default branch/revision, and start it once. Approve the environment deployment if prompted.
5. Confirm the run succeeds and open the deployment URL from its environment. For this project, the expected URL is `https://joe-mccarthy.github.io/odometer/`; verify the URL GitHub actually reports. Check stylesheet, favicon, copy button, `#features`/`#start` navigation and GitHub links. No custom domain, secrets, package installation, or application/database upload is required.

The workflow uses the official [GitHub static Pages template](https://github.com/actions/starter-workflows/blob/main/pages/static.yml), with its automatic push trigger removed and artifact path narrowed. See [custom Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) and [publishing-source settings](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).

### Preview the project subpath

To reproduce Pages project hosting without deploying, create a temporary directory containing an `odometer` directory, copy the contents of `marketing/` into it, and serve that temporary directory with `python3 -m http.server 8080 --directory <temporary-directory>`. Open `http://localhost:8080/odometer/` (including the trailing slash). Relative asset and fragment URLs must stay under `/odometer/`.

The terminal preview is explicitly illustrative, not a screenshot or live application. Product claims and setup commands follow the repository README. Update the site when supported features or installation requirements change. Add a canonical URL and absolute Open Graph URL/image only once the public deployment URL is known.

## Check

```sh
node --check marketing/script.js
```

Check desktop and narrow mobile widths, keyboard links, anchor navigation, and the copy button (including when clipboard access is unavailable). The site remains readable and all navigation works without JavaScript.
