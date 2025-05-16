import streamlit as st
import pandas as pd
from PIL import Image
import numpy as np
from ultralytics import YOLO
import cv2
from datetime import datetime
import sys
import yaml
import os


# Load datasets with caching
@st.cache_data
def load_data():
    try:
        non_boycott_df = pd.read_csv("cleaned_Non-Boycott.csv")
        alternatives_df = pd.read_csv("alternatives.csv")
        if 'product_name' not in non_boycott_df.columns or not all(col in alternatives_df.columns for col in ['boycotted_product', 'alternative1', 'alternative2']):
            st.error("Error: Required columns are missing in the CSV files.")
            return None, None
        return non_boycott_df, alternatives_df
    except Exception as e:
        st.error(f"Error loading CSV files: {e}")
        return None, None

non_boycott_df, alternatives_df = load_data()
if non_boycott_df is None or alternatives_df is None:
    st.stop()

# Load YOLO model with caching
@st.cache_resource
def load_model():
    try:
        model = YOLO('best.pt')  # Replace with your model path
        return model
    except Exception as e:
        st.error(f"Error loading YOLO model: {e}")
        return None

model = load_model()
if model is None:
    st.stop()

# Load class names from the model or YAML
class_names = []
if hasattr(model, 'names'):
    class_names = list(model.names.values()) if isinstance(model.names, dict) else list(model.names)
else:
    try:
        with open('data.yaml', 'r') as file:
            class_names = yaml.safe_load(file).get('names', [])
    except Exception as e:
        st.error(f"Error loading class names: {e}")
        st.stop()
class_names = [str(name) for name in class_names] or ["Unknown"]

# Initialize session state for reported products
if 'reported_products' not in st.session_state:
    st.session_state.reported_products = []

# Streamlit app
st.title("Product Detection and Classification")
st.header("Upload a Product Image")
st.write("Upload a JPG or PNG image to detect and classify products.")
st.write(f"Last updated: 02:34 PM EEST, Thursday, May 15, 2025")

uploaded_file = st.file_uploader("Select an image...", type=["jpg", "png"])

if uploaded_file is not None:
    try:
        # Display the image
        image = Image.open(uploaded_file)
        st.image(image, caption='Uploaded Image', use_container_width=True)

        # Preprocess the image for YOLO
        image_array = np.array(image)
        image_array = cv2.cvtColor(image_array, cv2.COLOR_RGBA2BGR) if image_array.shape[-1] == 4 else cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
        image_array = cv2.resize(image_array, (640, 640))

        # Perform detection with YOLO
        results = model.predict(image_array, conf=0.25)

        # Process detection results
        detected_products = []
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls)
                confidence = float(box.conf)
                class_name = class_names[class_id] if class_id < len(class_names) else "Unknown"
                detected_products.append((class_name, confidence))

        if detected_products:
            st.subheader("Detected Products:")
            for idx, (class_name, confidence) in enumerate(detected_products):
                st.write(f"- **{class_name}** (Confidence: {confidence:.2f})")
                if class_name in non_boycott_df['product_name'].values:
                    st.success(f"**{class_name}** is a safe product.")
                elif class_name in alternatives_df['boycotted_product'].values:
                    alternatives = alternatives_df[alternatives_df['boycotted_product'] == class_name][['alternative1', 'alternative2']].values[0]
                    st.warning(f"**Alternatives for {class_name}:**\n- {alternatives[0]}\n- {alternatives[1]}")
                else:
                    st.error(f"**{class_name}** is not recognized in our database.")
                    user_input = st.text_input(
                        "Please provide the name of this product to help us improve our system:",
                        key=f"report_{idx}_{len(st.session_state.reported_products)}"
                    )
                    if st.button("Submit", key=f"submit_{idx}") and user_input:
                        st.session_state.reported_products.append(user_input)
                        st.success("Thank you for your contribution. Your input helps us improve our product database.")
                        pd.DataFrame(st.session_state.reported_products, columns=['product_name']).to_csv('reported_products.csv', index=False)
        else:
            st.warning("No products were detected in the image. This could be due to image quality, lighting, or the product not being in our database.")
            user_input = st.text_input(
                "Please provide the name of the product in the image to help us improve our detection system:",
                key="no_detection_input"
            )
            if st.button("Submit", key="submit_no_detection") and user_input:
                st.session_state.reported_products.append(user_input)
                st.success("Thank you for your input. Your contribution helps us enhance our product database and improve detection accuracy.")
                pd.DataFrame(st.session_state.reported_products, columns=['product_name']).to_csv('reported_products.csv', index=False)

    except Exception as e:
        st.error(f"An error occurred while processing the image. Please try again or contact support if the issue persists.")
