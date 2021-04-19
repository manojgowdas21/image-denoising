import streamlit as st
import cv2      
import os,urllib
import numpy as np    
import tensorflow as tf
import time

def main():
    selected_box = st.sidebar.selectbox(
        'Choose an option..',
        ('About the Project','Evaluate the model','view source code')
        )
    
    #readme_text = st.markdown(get_file_content_as_string("readme.md"))
    
    if selected_box == 'About the Project':
        about()
        st.sidebar.success('To try by yourself select "Evaluate the model".')
    if selected_box == 'Evaluate the model':
        models()
    if selected_box=='view source code':
        st.markdown(get_file_content_as_string("app.py"))
        
        
def about():
    st.write("""
            # Image Denoising With Deep Learning Models
         """)

 
@st.cache
def get_models():
    print(tf.__version__)
    dncnn=tf.keras.models.load_model('dncnn.h5')
    dncnn_lite = tf.lite.Interpreter('dncnn2.tflite')
    dncnn_lite.allocate_tensors()
    
    return dncnn,dncnn_lite

def models():

    st.title('Denoise your image with deep learning models..')
        
        
    st.write('\n')
    
    choice=st.sidebar.selectbox("Choose how to load image",["Use Existing Images","Browse Image"])
    
    if choice=="Browse Image":
      uploaded_file = st.sidebar.file_uploader("Choose a image file", type="jpg")

      if uploaded_file is not None:
      # Convert the file to an opencv image.
        file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
        gt = cv2.imdecode(file_bytes, 1)
        prediction_ui(gt)
          
    if choice=="Use Existing Images":
    
      image_file_chosen = st.sidebar.selectbox('Select an existing image:', get_list_of_images())
      
      if image_file_chosen:
          gt=cv2.imread(os.getcwd()+'\\images\\'+image_file_chosen)
          prediction_ui(gt)


def prediction_ui(gt):

    models_load_state=st.text('\n Loading models..')
    dncnn,dncnn_lite=get_models()
    models_load_state.text('\n Models Loading..complete')
    
    dncnn_filesize=os.stat('dncnn.h5').st_size / (1024 * 1024)
    dncnnlite_filesize=os.stat('dncnn2.tflite').st_size / (1024 * 1024)
    
    noise_level = st.sidebar.slider("Pick the noise level", 0, 45, 0)
          
    ground_truth,noisy_image,patches_noisy=get_image(gt,noise_level=noise_level)
    st.header('Input Image')
    st.markdown('** Noise level : ** `%d`  ( Noise level `0` will be same as original image )'%(noise_level))
    st.image(noisy_image)
    if noise_level!=0:
      st.success('PSNR of Noisy image : %.3f db'%PSNR(ground_truth,noisy_image))
    submit = st.button('Predict Now')
          
            
    if submit and noise_level!=0:
        progress_bar = st.progress(0)
        start=time.time()
        progress_bar.progress(10)
        denoised_image=predict_fun(dncnn,patches_noisy,gt)
        progress_bar.progress(60)
        end=time.time()
        st.header('Denoised image using DnCNN model')
        st.markdown('( Size of the model is : `%.3f` MB ) ( Time taken for prediction : `%.3f` seconds )'%(dncnn_filesize,(end-start)))
        st.image(denoised_image)
        st.success('PSNR of denoised image : %.3f db  '%(PSNR(ground_truth,denoised_image)))
        #st.success('Time taken for the prediction : %.3f seconds'%(end-start))
        
        progress_bar.progress(70)
        start=time.time()
        denoised_image_lite=predict_fun_tflite(dncnn_lite,patches_noisy,gt)
        end=time.time()
        st.header('Denoised image using lite version of DnCNN model')
        st.markdown('( Size of the model is : `%.3f` MB ) ( Time taken for prediction : `%.3f` seconds )'%(dncnnlite_filesize,(end-start)))
        progress_bar.progress(100)
        st.image(denoised_image_lite)
        st.success('PSNR of denoised image : %.3f db  '%(PSNR(ground_truth,denoised_image_lite)))
        progress_bar.empty()
    elif submit==True and noise_level==0:
        st.error("Choose noise level")
def get_patches(image):
    '''This functions creates and return patches of given image with a specified patch_size'''
    image=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
    height, width , channels= image.shape
    crop_sizes=[1]
    patch_size=40
    patches = []
    for crop_size in crop_sizes: #We will crop the image to different sizes
        crop_h, crop_w = int(height*crop_size),int(width*crop_size)
        image_scaled = cv2.resize(image, (crop_w,crop_h), interpolation=cv2.INTER_CUBIC)
        for i in range(0, crop_h-patch_size+1, int(patch_size/1)):
            for j in range(0, crop_w-patch_size+1, int(patch_size/1)):
              x = image_scaled[i:i+patch_size, j:j+patch_size] # This gets the patch from the original image with size patch_size x patch_size
              patches.append(x)
    return patches



def create_image_from_patches(patches,image_shape):
  '''This function takes the patches of images and reconstructs the image'''
  image=np.zeros(image_shape) # Create a image with all zeros with desired image shape
  patch_size=patches.shape[1]
  p=0
  for i in range(0,image.shape[0]-patch_size+1,int(patch_size/1)):
    for j in range(0,image.shape[1]-patch_size+1,int(patch_size/1)):
      image[i:i+patch_size,j:j+patch_size]=patches[p] # Assigning values of pixels from patches to image
      p+=1
  return np.array(image)

def get_image(gt,noise_level):

  patches=get_patches(gt)
  height, width , channels= gt.shape
  test_image=cv2.resize(gt, (width//40*40,height//40*40), interpolation=cv2.INTER_CUBIC)
  patches=np.array(patches)
  ground_truth=create_image_from_patches(patches,test_image.shape)

  #predicting the output on the patches of test image
  patches = patches.astype('float32') /255.
  patches_noisy = patches+ tf.random.normal(shape=patches.shape,mean=0,stddev=noise_level/255) 
  patches_noisy = tf.clip_by_value(patches_noisy, clip_value_min=0., clip_value_max=1.)
  noisy_image=create_image_from_patches(patches_noisy,test_image.shape)
  
  return ground_truth/255.,noisy_image,patches_noisy
def predict_fun(model,patches_noisy,gt):

  height, width , channels= gt.shape
  gt=cv2.resize(gt, (width//40*40,height//40*40), interpolation=cv2.INTER_CUBIC)
  denoised_patches=model.predict(patches_noisy)
  denoised_patches=tf.clip_by_value(denoised_patches, clip_value_min=0., clip_value_max=1.)

  #Creating entire denoised image from denoised patches
  denoised_image=create_image_from_patches(denoised_patches,gt.shape)

  return denoised_image
  


  
def predict_fun_tflite(model,patches_noisy,gt):
    
  height, width , channels= gt.shape
  gt=cv2.resize(gt, (width//40*40,height//40*40), interpolation=cv2.INTER_CUBIC)
  
  denoised_patches=[]
  for p in patches_noisy:
    model.set_tensor(model.get_input_details()[0]['index'],tf.expand_dims(p,axis=0))
    model.invoke()
    pred=model.get_tensor(model.get_output_details()[0]['index'])
    pred=tf.squeeze(pred,axis=0)
    denoised_patches.append(pred)
  
  denoised_patches=np.array(denoised_patches)
  denoised_patches=tf.clip_by_value(denoised_patches, clip_value_min=0., clip_value_max=1.)

  #Creating entire denoised image from denoised patches
  denoised_image=create_image_from_patches(denoised_patches,gt.shape)

  return denoised_image  
  
def PSNR(gt, image, max_value=1):
    """"Function to calculate peak signal-to-noise ratio (PSNR) between two images."""
    height, width , channels= gt.shape
    gt=cv2.resize(gt, (width//40*40,height//40*40), interpolation=cv2.INTER_CUBIC)
    mse = np.mean((gt - image) ** 2)
    if mse == 0:
        return 100
    return 20 * np.log10(max_value / (np.sqrt(mse)))
    
def get_list_of_images():
    file_list = os.listdir(os.getcwd()+'\\images')
    return [str(filename) for filename in file_list if str(filename).endswith('.jpg')]
    
@st.cache(show_spinner=False)
def get_file_content_as_string(path):
    url = 'https://raw.githubusercontent.com/sunilbelde/Imagedenoising-dncnn-keras/master/' + path
    response = urllib.request.urlopen(url)
    return response.read().decode("utf-8")

if __name__ == "__main__":
    main()