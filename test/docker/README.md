# Docker Test Runner

This Dockerfile allows you to run Pavilion unit tests in a Linux container environment.

## Quick Start

### Build the image:
```bash
docker build -t pavilion-test .
```

### Run all tests:
```bash
docker run --rm pavilion-test
```

## Advanced Usage

### Build with a specific Python version:
```bash
docker build --build-arg PYTHON_VERSION=3.10 -t pavilion-test:py3.10 .
```

### Run specific tests:
```bash
# Run only a specific test pattern
docker run --rm pavilion-test ./test/run_tests -o 'BuildCmdTests.build'

# Run with verbose output
docker run --rm pavilion-test ./test/run_tests -v

# List all available tests
docker run --rm pavilion-test ./test/run_tests --ls
```

### Interactive debugging:
```bash
# Get a shell inside the container
docker run --rm -it pavilion-test /bin/bash

# Then run tests manually
./test/run_tests
```

### Mount local code for development:
```bash
# Mount your local source to test changes without rebuilding
docker run --rm -v $(pwd):/pavilion pavilion-test
```

### Access test output on failure:
```bash
# Run with volume mount to persist test output
docker run --rm -v $(pwd)/test-output:/pavilion/test/output pavilion-test
```

## What the Container Includes

- Python (default: 3.6, configurable via build arg)
- Test dependencies (matplotlib, pylint)
- Documentation dependencies (sphinx, sphinx_rtd_theme)
- Spack package manager (v1.0.2)

## Notes

- The container automatically sets up Spack during build (takes a few minutes)
- Test output is written to `test/output/`
