# Lambda container image for Brain Tumor MRI inference (PyTorch CPU)
# Base: AWS Lambda Python 3.11 runtime image

FROM public.ecr.aws/lambda/python:3.11

# Install system dependencies for Pillow
RUN yum install -y \
    libGL \
    && yum clean all

# Install numpy from PyPI first (pre-built wheel; avoids source build issues)
RUN pip install --no-cache-dir "numpy<2"

# Install CPU-only PyTorch (much smaller than CUDA build)
RUN pip install --no-cache-dir \
    torch torchvision \
    --index-url https://download.pytorch.org/whl/cpu

# Copy and install remaining Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir \
    Pillow boto3

# Copy handler
COPY handler.py ${LAMBDA_TASK_ROOT}/

# Lambda container entrypoint
CMD ["handler.handler"]
