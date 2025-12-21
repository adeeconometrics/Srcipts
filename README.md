# Srcipts 🛠️

A collection of self-contained Python automation scripts for media processing, document conversion, and file manipulation. Each script is designed to be independent and can be run with its specific dependencies managed through **uv** for efficient and modular dependency management.

## Features

- **Modular Dependency Management**: Each script has its own optional dependency group, reducing bloat
- **Fast Execution**: Leverages `uv` for rapid Python execution with dependency isolation
- **Self-Contained Scripts**: Each script is independent and can be used standalone
- **CUDA Support**: Optional GPU acceleration for image compression
- **CLI Interface**: Unified command-line interface to run any script

## Prerequisites

- **Python 3.13+**
- **uv** - Fast Python package installer and runner
  
### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or on macOS with Homebrew:
```bash
brew install uv
```

## Installation

Clone the repository and navigate to the project directory:

```bash
git clone <repository-url>
cd Srcipts
```

### Install Project (Optional)

If you want to install the project with all dependencies:

```bash
# Install with all optional dependencies
uv pip install -e ".[all]"

# Or install specific script dependencies
uv pip install -e ".[pixcomp]"      # For image compression
uv pip install -e ".[vid2gif]"      # For video to GIF conversion
```

## Usage

### Via CLI Command

The easiest way to run scripts is through the unified CLI:

```bash
# List all available scripts
srcipts --list

# Run a specific script
srcipts <script-name> [arguments...]
```

### Via Direct Script Execution

You can also run scripts directly using `uv run`:

```bash
# Run with automatic dependency installation
uv run --extra <script-name> src/<script-name>.py [arguments...]
```

### Via Manual Environment Activation

```bash
# Create and activate a virtual environment with all dependencies
uv venv
source .venv/bin/activate

# Install specific dependencies
uv pip install -e ".[pixcomp]"

# Run the script
python src/pixcomp.py [arguments...]
```

## Available Scripts

### 📸 `pixcomp` - Image Compression (PIL-based)

Compress images using PIL/Pillow with customizable quality settings.

**Dependencies**: `pillow`

**Usage**:
```bash
srcipts pixcomp /path/to/images /path/to/output [--method {jpeg,jpg,webp,png}]
```

**Example**:
```bash
srcipts pixcomp ./photos ./compressed_photos --method webp
```

**Features**:
- Multiple format support (JPEG, WebP, PNG)
- Configurable quality levels
- Batch processing

---

### ⚡ `cupixcomp` - CUDA-Accelerated Image Compression

High-performance image compression using NVIDIA CUDA with nvcomp library.

**Dependencies**: `numpy`, `pillow`, `cupy-cuda11x` (or `cupy-cuda12x` for CUDA 12)

**Requirements**:
- NVIDIA GPU with CUDA support
- CUDA Toolkit installed
- CuPy compatible with your CUDA version

**Usage**:
```bash
srcipts cupixcomp compress /path/to/images /path/to/output [--compressor {lz4,snappy,gdeflate,cascaded}]
srcipts cupixcomp decompress /path/to/compressed /path/to/output [--pattern *]
```

**Examples**:
```bash
# Compress images using LZ4 compression
srcipts cupixcomp compress ./photos ./compressed --compressor lz4

# Decompress previously compressed images
srcipts cupixcomp decompress ./compressed ./decompressed
```

**Features**:
- GPU-accelerated compression
- Multiple compression algorithms
- Metadata saving for perfect decompression
- Compression ratio reporting

---

### 🎬 `vid2gif` - Video to GIF Converter

Convert video files to animated GIFs with customizable parameters.

**Dependencies**: `imageio`, `imageio-ffmpeg`, `pillow`, `numpy`

**Usage**:
```bash
srcipts vid2gif -input /path/to/video.mp4 -output /path/to/output.gif
```

**Example**:
```bash
srcipts vid2gif -input ~/Videos/animation.mp4 -output animation.gif
```

**Features**:
- Customizable FPS and quality
- Automatic resizing
- Frame sampling optimization
- Supports all video formats (MP4, WebM, AVI, etc.)

---

### 📄 `pdf2xls` - PDF Document Processor

Convert PDF tables to Excel sheets or Markdown format.

**Dependencies**: `tabula-py`, `pandas`, `tabulate`, `openpyxl`

**Usage**:
```bash
srcipts pdf2xls -input document.pdf -output document.xlsx
```

**Example**:
```bash
srcipts pdf2xls -input invoice.pdf -output invoice.xlsx
```

**Features**:
- Extract tables from PDFs
- Convert to Excel with multiple sheets
- Markdown table export
- Automatic table detection

---

### 📥 `downloader` - YouTube Video Downloader

Download videos from YouTube with flexible resolution options.

**Dependencies**: `pytube`

**Usage**:
```bash
srcipts downloader -url "https://www.youtube.com/watch?v=..." -output /path/to/save
```

**Example**:
```bash
srcipts downloader -url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -output ~/Downloads
```

**Features**:
- Download at highest available resolution
- Specific resolution selection
- Automatic file naming
- Direct streaming without intermediate files

---

## Dependency Management Details

### Understanding Optional Dependencies

Each script is organized with its own dependency group:

```toml
[project.optional-dependencies]
pixcomp = ["pillow>=10.3.0"]
cupixcomp = ["numpy>=1.21.0", "pillow>=8.0.0", "cupy-cuda11x>=9.0.0"]
vid2gif = ["imageio>=2.34.1", "imageio-ffmpeg>=0.5.1", "pillow>=10.3.0", "numpy>=1.26.4"]
pdf2xls = ["tabula-py>=2.5.0", "pandas>=2.0.0", "tabulate>=0.9.0", "openpyxl>=3.0.0"]
downloader = ["pytube>=15.0.0"]
```

### Installing Only What You Need

```bash
# Install only for image compression
uv pip install -e ".[pixcomp]"

# Install for multiple specific scripts
uv pip install -e ".[pixcomp,vid2gif]"

# Install everything
uv pip install -e ".[all]"

# Install with development tools
uv pip install -e ".[dev]"
```

### Working with Different Python Versions

`uv` automatically manages Python versions:

```bash
# Use a specific Python version
uv run --python 3.13 src/pixcomp.py [args]

# Create a virtual environment with specific Python
uv venv --python 3.13
```

## Development

### Setting Up Development Environment

```bash
# Install with development dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/

# Lint code
ruff check src/

# Type checking
mypy src/
```

### Project Structure

```
Srcipts/
├── src/
│   ├── cli.py              # Unified CLI entry point
│   ├── pixcomp.py          # Image compression
│   ├── cupixcomp.py        # CUDA image compression
│   ├── vid2gif.py          # Video to GIF
│   ├── pdf2xls.py          # PDF processing
│   ├── downloader.py       # YouTube downloader
│   └── utils.py            # Shared utilities
├── data/                   # Sample data files
├── shell/                  # Shell scripts
├── pyproject.toml          # Project configuration with dependencies
├── README.md               # This file
└── LICENSE                 # Project license
```

## Advanced Usage

### Running Scripts with Custom Python Versions

```bash
# Run with Python 3.13
uv run --python 3.13 --extra pixcomp src/pixcomp.py [args]
```

### Creating a Dedicated Virtual Environment for a Script

```bash
# Create venv for a specific script
uv venv venv-pixcomp --python 3.13
source venv-pixcomp/bin/activate
uv pip install -e ".[pixcomp]"
python src/pixcomp.py [args]
```

### Batch Processing Multiple Scripts

```bash
# Process images with pixcomp, then convert video to gif
srcipts pixcomp ./input_images ./compressed_images
srcipts vid2gif -input ./video.mp4 -output ./output.gif
```

## Troubleshooting

### `uv` Command Not Found

Make sure `uv` is installed and in your PATH:

```bash
# Check installation
uv --version

# If not found, reinstall
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Script Not Found

Ensure you're running the command from the project root directory and using the correct script name:

```bash
# List available scripts
srcipts --list
```

### CUDA Errors (cupixcomp)

For CUDA-accelerated compression, ensure:
1. NVIDIA GPU drivers are installed: `nvidia-smi`
2. CUDA Toolkit is installed and properly configured
3. CuPy version matches your CUDA version

```bash
# Check CUDA compatibility
python -c "import cupy; print(cupy.cuda.is_available())"
```

### Missing Dependencies

If a script fails with import errors:

```bash
# Reinstall dependencies for the script
uv pip install -e ".[pixcomp]"  # Replace with your script name

# Or install all dependencies
uv pip install -e ".[all]"
```

## Performance Tips

1. **Use CUDA for Large Batches**: `cupixcomp` is significantly faster for processing thousands of images
2. **Leverage uv's Caching**: `uv` caches dependencies, making subsequent runs much faster
3. **Batch Processing**: Process multiple files in one command for better efficiency
4. **GPU Memory**: For `cupixcomp`, monitor GPU memory and adjust batch sizes accordingly


## License

See [LICENSE](LICENSE) for details.

