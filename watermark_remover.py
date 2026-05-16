import cv2
import os

class WatermarkRemover:
    @staticmethod
    def remove_tiktok_watermark(input_path, output_path):
        cap = cv2.VideoCapture(input_path)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')

        crop_top = int(height * 0.05)
        crop_bottom = int(height * 0.05)
        new_height = height - crop_top - crop_bottom

        out = cv2.VideoWriter(output_path, fourcc, fps, (width, new_height))

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            cropped = frame[crop_top:height-crop_bottom, 0:width]
            out.write(cropped)

        cap.release()
        out.release()
        return output_path

    @staticmethod
    def remove_instagram_watermark(input_path, output_path):
        cap = cv2.VideoCapture(input_path)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')

        crop_bottom = int(height * 0.08)
        new_height = height - crop_bottom

        out = cv2.VideoWriter(output_path, fourcc, fps, (width, new_height))

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            cropped = frame[0:new_height, 0:width]
            out.write(cropped)

        cap.release()
        out.release()
        return output_path

    @staticmethod
    def process_video(input_path, platform):
        output_path = input_path.replace('.mp4', '_clean.mp4')

        if 'tiktok' in platform.lower():
            return WatermarkRemover.remove_tiktok_watermark(input_path, output_path)
        elif 'instagram' in platform.lower():
            return WatermarkRemover.remove_instagram_watermark(input_path, output_path)

        return input_path
