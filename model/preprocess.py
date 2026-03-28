"""
Image preprocessing utilities for Brain Tumor MRI Classification.
Provides a PyTorch Dataset and standard ImageNet transforms.
"""

import io
import os

from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms


IMAGE_SIZE = (224, 224)
CLASSES    = ["glioma", "meningioma", "notumor", "pituitary"]
CLASS_TO_IDX = {cls: idx for idx, cls in enumerate(CLASSES)}
IDX_TO_CLASS = {idx: cls for idx, cls in enumerate(CLASSES)}

# Standard ImageNet normalisation used by torchvision pretrained models
TRAIN_TRANSFORMS = transforms.Compose([
    transforms.Resize((256, 256)),
    transforms.RandomCrop(IMAGE_SIZE),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(15),
    transforms.ColorJitter(brightness=0.2, contrast=0.2),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225]),
])

VAL_TRANSFORMS = transforms.Compose([
    transforms.Resize(IMAGE_SIZE),
    transforms.CenterCrop(IMAGE_SIZE),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225]),
])


class MRIDataset(Dataset):
    """PyTorch Dataset for the Brain Tumor MRI folder structure."""

    def __init__(self, split_dir: str, transform=None):
        self.samples   = []
        self.transform = transform

        for class_name in CLASSES:
            class_dir = os.path.join(split_dir, class_name)
            if not os.path.isdir(class_dir):
                print(f"Warning: directory not found: {class_dir}")
                continue
            label = CLASS_TO_IDX[class_name]
            for fname in os.listdir(class_dir):
                if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                    self.samples.append((os.path.join(class_dir, fname), label))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        img = Image.open(path).convert("RGB")
        if self.transform:
            img = self.transform(img)
        return img, label


def preprocess_image_bytes(image_bytes: bytes):
    """Preprocess raw image bytes into a normalised PyTorch tensor (1, C, H, W)."""
    import torch
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = VAL_TRANSFORMS(img)          # shape: (3, 224, 224)
    return tensor.unsqueeze(0)            # shape: (1, 3, 224, 224)
