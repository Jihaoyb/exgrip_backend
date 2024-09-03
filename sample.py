from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import requests
from PIL import Image
import torch
import clip
import io

app = FastAPI()

# Allow requests from any origin (you can restrict this to your frontend's domain)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the CLIP model
device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)

class ImageData(BaseModel):
    vehicleImgUrl: str
    dateTime: str
    id: str

class QueryRequest(BaseModel):
    query: str
    images: List[ImageData]

class QueryResponse(BaseModel):
    results: List[Dict[str, Any]]

@app.post("/search", response_model=QueryResponse)
async def search_images(request: QueryRequest):
    try:
        text_inputs = clip.tokenize([request.query]).to(device)
        image_features = []
        metadata = []

        for image_data in request.images:
            response = requests.get(image_data.vehicleImgUrl)
            img = Image.open(io.BytesIO(response.content))
            img_input = preprocess(img).unsqueeze(0).to(device)
            
            with torch.no_grad():
                image_feature = model.encode_image(img_input)
            image_features.append(image_feature)
            metadata.append({"id": image_data.id, "dateTime": image_data.dateTime})

        image_features = torch.cat(image_features)
        
        with torch.no_grad():
            text_features = model.encode_text(text_inputs)
            similarity = (100.0 * image_features @ text_features.T).squeeze(1).cpu().numpy()

        ranked_indices = similarity.argsort()[::-1][:5]
        results = [{"id": metadata[i]["id"], "dateTime": metadata[i]["dateTime"]} for i in ranked_indices]

        return QueryResponse(results=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))