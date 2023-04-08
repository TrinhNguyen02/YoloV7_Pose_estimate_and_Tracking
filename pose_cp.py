import os
import sys
import cv2
import time
import torch
import argparse
import numpy as np
from pathlib import Path
from numpy import random
from random import randint
import torch.backends.cudnn as cudnn

import matplotlib.pyplot as plt
from torchvision import transforms
from utils.datasets import letterbox
from utils.torch_utils import select_device
from models.experimental import attempt_load
from utils.general import non_max_suppression_kpt,strip_optimizer,xyxy2xywh
from utils.plots import output_to_keypoint, plot_skeleton_kpts,colors,plot_one_box_kpt, output_tracking

#For SORT tracking
import skimage
from sort import *

#For SORT tracking
import skimage
from sort import *

DIRECTORY_VIDEO_PATH="D:/DOCUMENTS/HK222/DA1/LRCN/LRCN_OP_YOLO/datos/NTURGBD/VIDEOS_50_120"
OUTPUT_DIRECTORY="D:/DOCUMENTS/HK222/DA1/LRCN/LRCN_OP_YOLO/datos/NTURGBD/DATOS-YOLO5"
weights = "D:/AI_MC/Action_Recognition/yolov7-pose-estimation/yolov7-w6-pose.pt"



def detect(poseweights=weights,source="football1.mp4",device='cpu',view_img=False,
        save_conf=False,line_thickness = 3,hide_labels=False, hide_conf=True, action = None):
    for idz, cls_ac in enumerate(['fighting', 'smoking', 'standing_up']):
        if action == cls_ac: action = idz
    frame_count = 0  #count no of frames
    total_fps = 0  #count total fps
    time_list = []   #list to store time
    fps_list = []    #list to store fps
    final_kpts = []
    #.... Initialize SORT .... 
    #......................... 
    sort_max_age = 5 
    sort_min_hits = 2
    sort_iou_thresh = 0.2
    sort_tracker = Sort(max_age=sort_max_age,
                       min_hits=sort_min_hits,
                       iou_threshold=sort_iou_thresh)
    #......................... 
        
    #........Rand Color for every trk.......
    rand_color_list = []
    for i in range(0,5005):
        r = randint(0, 255)
        g = randint(0, 255)
        b = randint(0, 255)
        rand_color = (r, g, b)
        rand_color_list.append(rand_color)
    #......................................

    device = select_device(device) #select device
    half = device.type != 'cpu'

    model = attempt_load(poseweights, map_location=device)  #Load model
    _ = model.eval()
    names = model.module.names if hasattr(model, 'module') else model.names  # get class names
   
    if str(source[0]).isdigit():    
        cap = cv2.VideoCapture(int(source))    #pass video to videocapture object
    else :
        cap = cv2.VideoCapture(source)    #pass video to videocapture object
   
    if (cap.isOpened() == False):   #check if videocapture not opened
        print('Error while trying to read video. Please check path again')
        raise SystemExit()

    while(True):
        frame_width = int(cap.get(3))  #get video frame width
        frame_height = int(cap.get(4)) #get video frame height

        
        vid_write_image = letterbox(cap.read()[1], (frame_width), stride=64, auto=True)[0] #init videowriter
        resize_height, resize_width = vid_write_image.shape[:2]
        out_video_name = f"{source.split('/')[-1].split('.')[0]}"
        out = cv2.VideoWriter(f"{source}_keypoint.mp4",
                            cv2.VideoWriter_fourcc(*'mp4v'), 30,
                            (resize_width, resize_height))

        while(cap.isOpened): #loop until cap opened or video not complete
        
            print("Frame {} Processing".format(frame_count+1))

            ret, frame = cap.read()  #get frame and success from video capture
            frame_h, frame_w, channels = frame.shape
            print("h", frame_h, "w", frame_w, ret)
            if ret: #if success is true, means frame exist
                orig_image = frame #store frame
                image = cv2.cvtColor(orig_image, cv2.COLOR_BGR2RGB) #convert frame to RGB
                image = letterbox(image, (frame_width), stride=64, auto=True)[0]
                image_ = image.copy()
                image = transforms.ToTensor()(image)
                image = torch.tensor(np.array([image.numpy()]))
            
                image = image.to(device)  #convert image data to device
                image = image.float() #convert image to float precision (cpu)
                start_time = time.time() #start time for fps calculation
            
                with torch.no_grad():  #get predictions
                    output_data, _ = model(image)

                output_data = non_max_suppression_kpt(output_data,   #Apply non max suppression
                                            0.25,   # Conf. Threshold.
                                            0.65, # IoU Threshold.
                                            nc=model.yaml['nc'], # Number of classes.
                                            nkpt=model.yaml['nkpt'], # Number of keypoints.
                                            kpt_label=True)
            
                output = output_to_keypoint(output_data)

                im0 = image[0].permute(1, 2, 0) * 255 # Change format [b, c, h, w] to [h, w, c] for displaying the image.
                im0 = im0.cpu().numpy().astype(np.uint8)
                
                im0 = cv2.cvtColor(im0, cv2.COLOR_RGB2BGR) #reshape image format to (BGR)
                gn = torch.tensor(im0.shape)[[1, 0, 1, 0]]  # normalization gain whwh

                for i, pose in enumerate(output_data):  # detections per image

                    if len(output_data):  #check if no pose
                        for c in pose[:, 5].unique(): # Print results
                            n = (pose[:, 5] == c).sum()  # detections per class
                            print("Objects in Current Frame : {}".format(n))
                               #..................USE TRACK FUNCTION....................
                            #pass an empty array to sort
                            dets_to_sort = np.empty((0,6))
                            
                            # NOTE: We send in detected object class too
                        for det_index,(*xyxy, conf, cls) in enumerate(reversed(pose[:,:6])):
                            dets_to_sort = np.vstack((dets_to_sort, np.array([int(xyxy[0]), int(xyxy[1]),int(xyxy[2]),int(xyxy[3]), conf, cls])))
                            # print(dets_to_sort)

                        # Run SORT
                        tracked_dets = sort_tracker.update(dets_to_sort)
                        tracks =sort_tracker.getTrackers()
                        bb_track = tracked_dets 
                        bb_track= bb_track.tolist()
                        bb_track = [[int(x) for x in bbox[:4]] + [int(bbox[-1])] for bbox in bb_track]

                        kpt_t = []
                        txt_str = ""
                        for det_index, (*xyxy, conf, cls) in enumerate(reversed(pose[:,:6])): #loop over poses for drawing on frame
                            c = int(cls)  # integer class
                            
                            kpts = pose[det_index, 6:]
                            kpt_t.append(kpts.tolist())

                            label = None if opt.hide_labels else (names[c] if opt.hide_conf else f'{names[c]} {conf:.2f}')
                            plot_one_box_kpt(xyxy, im0, label=label, color=colors(c, True), 
                                        line_thickness=opt.line_thickness,kpt_label=True, kpts=kpts, steps=3, 
                                        orig_shape=im0.shape[:2], conf = conf , cls = cls, names= names, sort_tracker = sort_tracker, rand_color_list =  rand_color_list,tracks = tracks, tracked_dets = tracked_dets )
                                
                        kptDt = output_tracking(bboxs =bb_track, keypoints = kpt_t, height = frame_h, width =frame_w, cls =1, frame = frame_count )
                        # print(kptDt)
                        final_kpts.append(kptDt)

                end_time = time.time()  #Calculatio for FPS
                fps = 1 / (end_time - start_time)
                total_fps += fps
                frame_count += 1
                
                fps_list.append(total_fps) #append FPS in list
                time_list.append(end_time - start_time) #append time in list
                
                # Stream results
                if view_img:
                    cv2.imshow("YOLOv7 Pose Estimation Demo", im0)
                    cv2.waitKey(1)  # 1 millisecond

                out.write(im0)  #writing the video frame

            else:
                break

        cap.release()
        # cv2.destroyAllWindows()
        avg_fps = total_fps / frame_count
        print(f"Average FPS: {avg_fps:.3f}")
        
        #plot the comparision graph
        # plot_fps_time_comparision(time_list=time_list,fps_list=fps_list)
    return final_kpts


#function for plot fps and time comparision graph
def plot_fps_time_comparision(time_list,fps_list):
    plt.figure()
    plt.xlabel('Time (s)')
    plt.ylabel('FPS')
    plt.title('FPS and Time Comparision Graph')
    plt.plot(time_list, fps_list,'b',label="FPS & Time")
    plt.savefig("FPS_and_Time_Comparision_pose_estimate.png")


start=sys.argv[1]

for base, dirs, files in sorted(os.walk(DIRECTORY_VIDEO_PATH)):
    action = base.split(os.path.sep)[-1]
    # print(files)

    if start != "VIDEOS":    
        print("Process accion: " + action + " ...")
        # Crear directorio si no existe
        if not os.path.exists(OUTPUT_DIRECTORY + '/' + start):
            print(OUTPUT_DIRECTORY + '/' + start)
            os.mkdir(OUTPUT_DIRECTORY + '/' + start)        
        

    # for video in files:
    #     print(video)
    #     print("--Procesando: " + video) 
    #     video_extension = os.path.splitext(video)[0]

    #     # Si el archivo ya existe lo omitimos
    #     dat_ouput = OUTPUT_DIRECTORY + "/" + action + "/" + video_extension + ".dat"
    #     if not os.path.exists(dat_ouput):  
    
    #         result = detect(source = (DIRECTORY_VIDEO_PATH + '/' + action + '/' + video), action = start)
    
    #         # Escribimos el fichero
    #         with open(dat_ouput, 'a+') as f:
    #             f.write(result)
    #             f.close()
    
# print("Proceso terminado correctamente.")