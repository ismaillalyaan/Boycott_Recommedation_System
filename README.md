# 🛑 Product Detection and Boycott Advisory System
A Streamlit web application that detects products in uploaded images using **YOLOv8** and flags boycotted products based on ethical consumption data. It also suggests non-boycotted alternatives using **semantic similarity** techniques.

🚀 **Live Demo**: boycottrecommedationsystem.streamlit.app

---

## 📌 Features

- 📁 **Image Upload**  
  Upload JPG/PNG images for product detection.

- 🔍 **YOLOv8 Detection**  
  Detects products using a custom-trained YOLOv8 model with confidence scores.

- 🚫 **Boycott Check**  
  Highlights products listed in the boycott database.

- 🔄 **Ethical Alternatives**  
  Recommends similar ethical products via semantic similarity matching.

- 📝 **User Reporting**  
  Crowdsources unknown products to refine the database.

- ⏱️ **Real-Time Updates**  
  Timestamped updates enable a dynamic and evolving system.

---

## 📂 Dataset Structure

### 🛑 Boycott Lists
- `Boycott.csv`: Raw list of boycotted products
- `cleaned_Boycott.csv`: Preprocessed version with simplified product descriptions

### ✅ Non-Boycott Lists
- `Non-Boycott.csv`: Raw list of approved products
- `cleaned_Non-Boycott.csv`: Preprocessed ethical alternatives

---

## 🧠 Model Architecture

### 1. Object Detection
- Model: `YOLOv8` (`best.pt`)
- Config: `data.yaml` for class labels

### 2. Semantic Matching
- Model: `all-MiniLM-L6-v2` sentence transformer
- Cosine similarity threshold: **0.45**
- Output: `alternatives.csv` — Recommended ethical replacements

