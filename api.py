from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import boto3
from typing import Optional, List
from boto3.dynamodb.conditions import Attr, And, Or, Not, Between

app = FastAPI()

# Initialize DynamoDB resource using the default credentials from aws configure
dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
table = dynamodb.Table('exgrip_combinations')

# Define the model for the input data
class ItemModel(BaseModel):
    id: Optional[str]
    spindle: Optional[str]
    length: Optional[str]  # Now length is a string that can represent a range
    holderAngle: Optional[str]
    extensionAngle: Optional[str]
    toolType: Optional[str]
    boreDiameter: Optional[str] # Standard End Mills
    cuttingDiameter: Optional[str] # EXGRIP Milling Cutter
    edgeRadius: Optional[str] # EXGRIP Ball Cutter
    thread: Optional[str] # Exchangeable Head Mills
    productSKUClampingExtension: Optional[str] # Will be used while return result
    productSKUExtensionAdapter: Optional[str] # Will be used while return result
    productSKUMasterHolder: Optional[str] # Will be used while return result

@app.post("/process-data/", response_model=List[ItemModel])
async def process_data(item: ItemModel):
    try:
        # Initialize a filter expression
        filter_expression = None

        # Dynamically build the filter expression based on the provided fields
        if item.spindle:
            filter_expression = Attr('spindle').eq(item.spindle)
        
        # Handle length range
        if item.length:
            length_filter = parse_length_range(item.length)
            if length_filter:
                filter_expression = filter_expression & length_filter if filter_expression else length_filter
        
        if item.holderAngle:
            filter_expression = filter_expression & Attr('holderAngle').eq(item.holderAngle) if filter_expression else Attr('holderAngle').eq(item.holderAngle)
        if item.extensionAngle:
            filter_expression = filter_expression & Attr('extensionAngle').eq(item.extensionAngle) if filter_expression else Attr('extensionAngle').eq(item.extensionAngle)
        if item.toolType:
            if item.toolType == 'Standard End Mills':
                filter_expression = filter_expression & Attr('boreDiameter').eq(item.boreDiameter) if filter_expression else Attr('boreDiameter').eq(item.boreDiameter)
            elif item.toolType == 'EXGRIP Milling Cutter':
                filter_expression = filter_expression & Attr('cuttingDiameter').eq(item.cuttingDiameter) if filter_expression else Attr('cuttingDiameter').eq(item.cuttingDiameter)
            elif item.toolType == 'EXGRIP Ball Cutter':
                filter_expression = filter_expression & Attr('edgeRadius').eq(item.edgeRadius) if filter_expression else Attr('edgeRadius').eq(item.edgeRadius)
            elif item.toolType == 'Exchangeable Head Mills':
                filter_expression = filter_expression & Attr('thread').eq(item.thread) if filter_expression else Attr('thread').eq(item.thread)
            

        # Ensure at least one filter is provided
        if not filter_expression:
            raise HTTPException(status_code=400, detail="No valid fields provided for filtering.")

        # Perform the scan operation
        response = table.scan(FilterExpression=filter_expression)

        # Get the matched items
        items = response.get('Items', [])
        if not items:
            raise HTTPException(status_code=404, detail="No items found matching the criteria.")
        
        # Convert the matched items to ItemModel instances
        matched_items = [{"holderSKU": item.productSKUMasterHolder, 
                          "adapterSKU": item.productSKUExtensionAdapter,
                          "clampSKU": item.productSKUClampingExtension,
                          "holderAngle": item.holderAngle,
                          "extensionAngle": item.extensionAngle,
                          'boreDiameter': item.boreDiameter,
                          'cuttingDiameter': item.cuttingDiameter,
                          'edgeRadius': item.edgeRadius,
                          'thread': item.thread
                         } for item in items]
        
        return ItemModel(matched_items=matched_items)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def parse_length_range(length: str):
    """
    Parses the length string from the frontend and returns a corresponding DynamoDB condition expression.
    Example length strings:
    - '<=200'
    - '201-250'
    - '>600'
    """
    if length.startswith('<='):
        # Length is less than or equal to a value
        value = int(length[2:])
        return Attr('length').lte(value)
    elif '-' in length:
        # Length is within a range
        start, end = map(int, length.split('-'))
        return Attr('length').between(start, end)
    elif length.startswith('>'):
        # Length is greater than a value
        value = int(length[1:])
        return Attr('length').gt(value)
    else:
        # Length is an exact value (default case)
        value = int(length)
        return Attr('length').eq(value)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
