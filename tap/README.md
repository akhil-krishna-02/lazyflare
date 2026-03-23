# Homebrew Tap for LazyFlare

To make LazyFlare installable via `brew install akhil-krishna-02/tap/lazyflare`, you will need to create a new repository on GitHub named `homebrew-tap`.

Inside that repository, place this file under `Formula/lazyflare.rb`:

```ruby
class Lazyflare < Formula
  include Language::Python::Virtualenv

  desc "Cloudflare in your terminal"
  homepage "https://github.com/akhil-krishna-02/lazyflare"
  url "https://github.com/akhil-krishna-02/lazyflare/archive/refs/tags/v0.3.0.tar.gz"
  sha256 "REPLACE_WITH_SHA256_OF_ARCHIVE"
  license "MIT"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/lazyflare", "--help"
  end
end
```

### Steps to Release

1. **Publish to PyPI:**
   ```bash
   pip install build twine
   python -m build
   twine upload dist/*
   ```

2. **Tag your GitHub Release:**
   ```bash
   git tag v0.3.0
   git push origin v0.3.0
   ```

3. **Update the Homebrew Formula:**
   Whenever you release a new version, run this command to get the SHA256 of your tarball:
   ```bash
   curl -sL https://github.com/akhil-krishna-02/lazyflare/archive/refs/tags/v0.3.0.tar.gz | shasum -a 256
   ```
   Paste that hash into the `lazyflare.rb` file in your `homebrew-tap` repository and commit it.

Once done, anyone can run:
```bash
brew install akhil-krishna-02/tap/lazyflare
```