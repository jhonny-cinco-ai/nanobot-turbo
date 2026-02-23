---
description: How to build and upload Nanofolks to PyPI
---

Follow these steps to publish the `nanofolks` package to PyPI.

### 1. Prerequisites
- Create an account on [PyPI](https://pypi.org/) and/or [TestPyPI](https://test.pypi.org/).
- Generate an **API Token** from your Account Settings.
- Install the build tools:
  ```bash
  pip install --upgrade build twine
  ```

### 2. Prepare the Version
Check `pyproject.toml` and ensure the `version` (currently `0.1.3.post6`) is updated if you are making a new release.

### 3. Build the Package
Clean any previous builds and generate the distribution files:
```bash
rm -rf dist/ build/ *.egg-info
python -m build
```
This will create a `.tar.gz` (source distribution) and a `.whl` (built distribution) in the `dist/` folder.

### 4. Verify the Build
Check if the generated files are valid:
```bash
twine check dist/*
```

### 5. Upload to TestPyPI (Optional but Recommended)
Test the upload process first:
// turbo
```bash
python -m twine upload --repository testpypi dist/*
```
*Tip: Use `__token__` as the username and your TestPyPI API token as the password.*

### 6. Upload to PyPI
When ready for the real deal:
// turbo
```bash
python -m twine upload dist/*
```
*Tip: Use `__token__` as the username and your PyPI API token as the password.*

### 7. Verify the Installation
Once uploaded, try installing it in a fresh environment:
```bash
pip install nanofolks
```
