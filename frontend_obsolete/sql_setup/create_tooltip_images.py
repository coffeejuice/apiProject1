import os
from PIL import Image, ImageDraw, ImageFont


os.chdir('images')

# Set the dimensions of the images
img_width = 500
img_height = 500

# Create a font object
font = ImageFont.truetype("arial.ttf", 470)

left, top, right, bottom = range(4)

# Loop through the range of numbers and create an image for each
for i in range(1, 100):
    # Create a new image with a white background
    img = Image.new(mode='RGB', size=(img_width, img_height), color='white')

    # Get a drawing context
    draw = ImageDraw.Draw(img)

    # Create a text box for the number
    text_box = draw.textbbox((0, 0), str(i), font=font)

    # Calculate the x and y coordinates for the center of the image
    x = (img_width - (text_box[right] - text_box[left])) / 2
    y = (img_height - (text_box[bottom] - text_box[top])) / 2 - text_box[top]

    # Draw the number in the center of the image
    draw.text((x, y), str(i), fill='black', font=font)

    # Save the image with the appropriate file name
    file_name = f"tooltip_image_{i}.png"
    img.save(file_name)
