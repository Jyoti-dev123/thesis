"""
CNN Model Training for Brain Tumor MRI Classification.

Architecture: MobileNetV2 (torchvision pretrained) fine-tuned for 4-class classification:
  - glioma, meningioma, notumor, pituitary

Training strategy:
  Phase 1 — freeze backbone, train classification head   (EPOCHS epochs)
  Phase 2 — unfreeze full network, fine-tune at lower LR (FINETUNE_EPOCHS epochs)

Exports:
  - brain_tumor_model.pt   (full PyTorch model via torch.save)
  - brain_tumor_model.onnx (ONNX opset-17 for portable inference)
  - class_labels.json

Usage:
    python model/train_model.py
"""

import json
import os
import sys
import copy

import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import ReduceLROnPlateau
from torch.utils.data import DataLoader, random_split
from torchvision import models
from sklearn.metrics import classification_report, confusion_matrix
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.preprocess import MRIDataset, TRAIN_TRANSFORMS, VAL_TRANSFORMS, CLASSES

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
TRAIN_DIR   = os.path.join(DATASET_DIR, "Training")
TEST_DIR    = os.path.join(DATASET_DIR, "Testing")
MODEL_DIR   = os.path.join(BASE_DIR, "model")
PT_PATH     = os.path.join(MODEL_DIR, "brain_tumor_model.pt")
ONNX_PATH   = os.path.join(MODEL_DIR, "brain_tumor_model.onnx")
LABELS_PATH = os.path.join(MODEL_DIR, "class_labels.json")

# ---------------------------------------------------------------------------
# Hyperparameters
# ---------------------------------------------------------------------------
BATCH_SIZE      = 32
EPOCHS          = 20      # Phase 1 (frozen backbone)
FINETUNE_EPOCHS = 10      # Phase 2 (full network)
LEARNING_RATE   = 1e-3
FINETUNE_LR     = 1e-4
VAL_SPLIT       = 0.15
NUM_CLASSES     = len(CLASSES)
NUM_WORKERS     = 4


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

def build_model(num_classes: int = NUM_CLASSES) -> nn.Module:
    """MobileNetV2 with a custom classification head."""
    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)

    # Freeze all backbone parameters
    for param in model.parameters():
        param.requires_grad = False

    # Replace classifier head
    in_features = model.classifier[1].in_features
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.4),
        nn.Linear(in_features, 256),
        nn.ReLU(inplace=True),
        nn.Dropout(p=0.3),
        nn.Linear(256, num_classes),
    )
    return model


def unfreeze_backbone(model: nn.Module) -> None:
    """Unfreeze all parameters for fine-tuning Phase 2."""
    for param in model.parameters():
        param.requires_grad = True


# ---------------------------------------------------------------------------
# Training helpers
# ---------------------------------------------------------------------------

def train_one_epoch(model, loader, criterion, optimizer, device):
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0
    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        running_loss += loss.item() * images.size(0)
        _, predicted = outputs.max(1)
        correct += predicted.eq(labels).sum().item()
        total += labels.size(0)
    return running_loss / total, correct / total


def evaluate(model, loader, criterion, device):
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0
    with torch.no_grad():
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)
            running_loss += loss.item() * images.size(0)
            _, predicted = outputs.max(1)
            correct += predicted.eq(labels).sum().item()
            total += labels.size(0)
    return running_loss / total, correct / total


def run_phase(model, train_loader, val_loader, criterion, optimizer,
              scheduler, epochs, device, checkpoint_path, phase_name):
    """Run a training phase, return best model weights."""
    best_val_acc = 0.0
    best_weights = copy.deepcopy(model.state_dict())
    patience_counter = 0
    patience = 5

    for epoch in range(1, epochs + 1):
        train_loss, train_acc = train_one_epoch(
            model, train_loader, criterion, optimizer, device)
        val_loss, val_acc = evaluate(
            model, val_loader, criterion, device)

        scheduler.step(val_loss)

        print(f"  [{phase_name}] Epoch {epoch:3d}/{epochs}  "
              f"train_loss={train_loss:.4f}  train_acc={train_acc*100:.2f}%  "
              f"val_loss={val_loss:.4f}  val_acc={val_acc*100:.2f}%")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_weights = copy.deepcopy(model.state_dict())
            torch.save(model, checkpoint_path)
            print(f"    -> Saved best model (val_acc={best_val_acc*100:.2f}%)")
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"    Early stopping triggered at epoch {epoch}.")
                break

    model.load_state_dict(best_weights)
    return model


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Brain Tumor MRI Classification — PyTorch Training")
    print("=" * 60)

    # Device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\nDevice: {device}")
    if device.type == "cuda":
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
        print(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    # --- Datasets ---
    print("\n[1/5] Preparing datasets...")
    full_train = MRIDataset(TRAIN_DIR, transform=TRAIN_TRANSFORMS)
    test_ds    = MRIDataset(TEST_DIR,  transform=VAL_TRANSFORMS)

    val_size   = int(len(full_train) * VAL_SPLIT)
    train_size = len(full_train) - val_size
    train_ds, val_ds = random_split(
        full_train, [train_size, val_size],
        generator=torch.Generator().manual_seed(42),
    )
    # Val set should use val transforms — wrap it
    val_ds.dataset = MRIDataset(TRAIN_DIR, transform=VAL_TRANSFORMS)

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE,
                              shuffle=True,  num_workers=NUM_WORKERS, pin_memory=True)
    val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE,
                              shuffle=False, num_workers=NUM_WORKERS, pin_memory=True)
    test_loader  = DataLoader(test_ds,  batch_size=BATCH_SIZE,
                              shuffle=False, num_workers=NUM_WORKERS, pin_memory=True)

    print(f"  Train: {train_size}  Val: {val_size}  Test: {len(test_ds)}")

    # Class distribution
    from collections import Counter
    label_counts = Counter(label for _, label in full_train.samples)
    print("  Class distribution (full training set):")
    for idx, count in sorted(label_counts.items()):
        print(f"    {CLASSES[idx]}: {count}")

    # --- Build model ---
    print("\n[2/5] Building MobileNetV2 model...")
    model = build_model(NUM_CLASSES).to(device)

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total     = sum(p.numel() for p in model.parameters())
    print(f"  Trainable params: {trainable:,} / {total:,}")

    criterion = nn.CrossEntropyLoss()

    # --- Phase 1: train classification head only ---
    print("\n[3/5] Phase 1 — training classification head (backbone frozen)...")
    optimizer1 = optim.Adam(filter(lambda p: p.requires_grad, model.parameters()),
                            lr=LEARNING_RATE)
    scheduler1  = ReduceLROnPlateau(optimizer1, mode="min", factor=0.5, patience=3)

    model = run_phase(
        model, train_loader, val_loader, criterion,
        optimizer1, scheduler1, EPOCHS, device, PT_PATH, "Phase1",
    )

    # --- Phase 2: fine-tune full network ---
    print("\n[4/5] Phase 2 — fine-tuning full network (all layers unfrozen)...")
    unfreeze_backbone(model)
    optimizer2 = optim.Adam(model.parameters(), lr=FINETUNE_LR)
    scheduler2  = ReduceLROnPlateau(optimizer2, mode="min", factor=0.5, patience=3)

    model = run_phase(
        model, train_loader, val_loader, criterion,
        optimizer2, scheduler2, FINETUNE_EPOCHS, device, PT_PATH, "Phase2",
    )

    # --- Evaluate on test set ---
    print("\n[5/5] Evaluating on test set...")
    test_loss, test_acc = evaluate(model, test_loader, criterion, device)
    print(f"  Test Accuracy: {test_acc * 100:.2f}%")
    print(f"  Test Loss:     {test_loss:.4f}")

    all_preds, all_labels = [], []
    model.eval()
    with torch.no_grad():
        for images, labels in test_loader:
            outputs = model(images.to(device))
            preds   = outputs.argmax(dim=1).cpu().numpy()
            all_preds.extend(preds.tolist())
            all_labels.extend(labels.numpy().tolist())

    print("\nClassification Report:")
    print(classification_report(all_labels, all_preds, target_names=CLASSES))
    print("Confusion Matrix:")
    print(confusion_matrix(all_labels, all_preds))

    # --- Save full model ---
    torch.save(model, PT_PATH)
    print(f"\nModel saved to: {PT_PATH}")

    # --- Export to ONNX ---
    print("Exporting to ONNX...")
    dummy_input = torch.randn(1, 3, 224, 224, device=device)
    torch.onnx.export(
        model,
        dummy_input,
        ONNX_PATH,
        export_params=True,
        opset_version=18,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
    )
    print(f"ONNX model saved to: {ONNX_PATH}")

    # --- Save class labels ---
    with open(LABELS_PATH, "w") as f:
        json.dump({
            "classes":      CLASSES,
            "class_to_idx": {c: i for i, c in enumerate(CLASSES)},
        }, f, indent=2)
    print(f"Class labels saved to: {LABELS_PATH}")

    print("\nDone.")


if __name__ == "__main__":
    main()

