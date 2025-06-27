import pyqrcode
import pandas as pd
import numpy as np
import png
import urllib.request
import unicodedata
import argparse
import logging
import sys
import yaml
from PIL import Image, ImageFile, ImageFont, ImageDraw
import os

font = ImageFont.truetype("fonts/OpenSans-Bold.ttf", 140)
font2 = ImageFont.truetype("fonts/OpenSans-Regular.ttf", 70)
font3 = ImageFont.truetype("fonts/OpenSans-Semibold.ttf", 80)

font_first_name = None
font_last_name = None
font_title = None
font_company = None
font_attendee_type = None

def main():

    logging.basicConfig(
            format='%(asctime)s - %(levelname)s - %(message)s',
            level=logging.INFO,
            handlers=[
                        logging.FileHandler("confbadger.log"),  # Save logs to this file
                        logging.StreamHandler()                 # Also print to the terminal
            ])
    logger = logging.getLogger(__name__)
    sys.stdout.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(description='Generating conference badges.')

    parser.add_argument('--data', default="data.csv",
                            help='List of attendees in the CSV format as exported from Bevy. Default is data.csv')
    parser.add_argument('--save-path', default="./codes",
                            help='Path to save the generated badges. Default is ./codes')
    parser.add_argument('--template', default="KCDAMS2023_Badge_Template.png",
                            help='Template for the badges. Default is the example KCDAMS2023_Badge_Template.png file')
    parser.add_argument('--config', default="config.yaml",
                            help='Config file. Default is config.yaml.')
    parser.add_argument('--pre-order-data',
                            help='Optional data file of the Pre order form from Bevy. To utilize information form here add a pre-order-data section to config.yaml')
    parser.add_argument('--results',
                            help='Scan sesults order list. ConfBadger produces a csv file of the results based on this.')
    parser.add_argument('--debug', action="store_true",
                            help='Print debug logs.')
    args = parser.parse_args()
    # print(args)
    if args.debug:
            logger.setLevel(logging.DEBUG)
            logger.debug("Debug logging is ON")

    data_file   = args.data
    save_path  = args.save_path
    template   = args.template
    config_file = args.config
    pre_order_data = None
    if args.pre_order_data:
        pre_order_data = args.pre_order_data

    logger.debug(f"Data file is {data_file}")
    logger.debug(f"Save path file is {save_path}")
    logger.debug(f"Template is {template}")
    logger.debug(f"Config file is {config_file}")
    logger.debug(f"Pre order data {pre_order_data}")

    if args.results:
           logger.debug(f"Order number list result file received ({args.results})")
           df_orders = get_data_from_ticket_numbers(args.results,
                                                    data_file,
                                                    pre_order_data,
                                                    config_file)
           
           df_orders.to_csv(sys.stdout, index=False)
           sys.exit(0)

            
    createBadge(template,
                save_path,
                data_file,
                config_file,
                pre_order_data)

def createBadge(template = "KCDAMS2023_Badge_Template.png",
                save_path = "codes",
                data_file = "data.csv",
                config_file = "config.yaml", 
                pre_order_data = None):
    
    logger = logging.getLogger(__name__)
    logger.debug(f"template: {template}, save_path: {save_path}, data_file: {data_file}, config_file: {config_file}")

    # Ensure both directories exist
    os.makedirs("badges", exist_ok=True)
    os.makedirs(save_path, exist_ok=True)
    
    with open(config_file, 'r') as f:
        config_data = yaml.load(f, Loader=yaml.SafeLoader)
    df = read_and_extend_data(data_file, pre_order_data, config_data)

    # Count of successfully created badges
    badge_count = 0
    qr_count = 0

    #logger.debug(f"Df post merge: {df.columns}")
    for index, values in df.iterrows():
        try:
            order_number            = values["Order number"]        
            ticket_number           = values["Ticket number"]
            firstname               = values["First Name"]
            lastname                = values["Last Name"]
            email                   = values["Email"]
            twitter                 = values["Twitter"]
            company                 = values["Company"]
            title                   = values["Title"]
            featured                = values["Featured"]
            ticket_title            = values["Ticket title"]
            ticket_venue            = values["Ticket venue"]
            access_code             = values["Access code"]
            price                   = values["Price"]
            currency                = values["Currency"]
            number_of_tickets       = values["Number of tickets"]
            paid_by_name            = values["Paid by (name)"]
            paid_by_email           = values["Paid by (email)"]
            paid_date               = values["Paid date (UTC)"]
            checkin_date            = values["Checkin Date (UTC)"]
            ticket_price_paid       = values["Ticket Price Paid"]

            ImageFile.LOAD_TRUNCATED_IMAGES = True
 
            attendee_type = "attendee"
            color = str_to_tuple(next((item["color"] for item in config_data["attendee-types"] if item.get("name") == "Attendee"), None))
            background_size = next((item["background-size"] for item in config_data["attendee-types"] if item.get("name") == "Attendee"), None)
            for attendee in config_data["attendee-types"]:
                    if ticket_title in attendee["ticket-titles"]:
                            logger.debug(f"name: {firstname} {lastname}, ticket type: {attendee['name']}")
                            attendee_type = attendee["name"]
                            color = str_to_tuple(attendee["color"])
            
            template = "5.png"    
            print(attendee_type)
            if attendee_type == "Volunteer":
                template = "1.png"
            if attendee_type == "Speaker":
                template = "2.png"
            if attendee_type == "Organizer":
                template = "3.png"
            if attendee_type == "Sponsor":
                template = "4.png"


            img_base = Image.open(template).convert("RGB")
            logger.debug(f"Handling {lastname}, {firstname} , {index}")
            #logger.debug(f'QR Code status: {config_data["qr-code"]["status"]}')
            add_qr = False
            # Preserving default behaviour. If qr-code or the status is not defined the VCARD is added.        
            if (not "qr-code" in config_data) or config_data["qr-code"]["status"] == "false":
               add_qr = False    
            elif (not "status" in config_data["qr-code"]) or (config_data["qr-code"]["status"] == "vcard"):
                    add_qr = True
                    data = f'''BEGIN:VCARD
N:{lastname};{firstname};
FN:{lastname}+{firstname}
EMAIL;WORK;INTERNET:{email}
ORG:CNDNL2025
VERSION:3.0
END:VCARD'''
                    scale="4"
            elif config_data["qr-code"]["status"] == "hash":
                    add_qr = True
                    data = f'{ticket_number}'
                    scale="10"
            if add_qr:
                    # Create QR code
                    qr_filename = f"{save_path}/{lastname}_{firstname}_{ticket_number}.png"
                    qrcode = pyqrcode.create(unicodedata.normalize('NFKD', data).encode('ascii','ignore').decode('ascii'))
                    qrcode.png(qr_filename, scale=scale)
                    qr_count += 1
                    
                    # Opening the secondary image (overlay image)
                    img_qcode = Image.open(qr_filename).convert("RGB")
                    
                    # Pasting qrcode image on top of template image 
                    # starting at coordinates from the position conf parameter
                    img_base.paste(img_qcode, str_to_tuple(config_data["qr-code"]["position"]))

            draw = ImageDraw.Draw(img_base)
            for item in config_data.get("data", []):
                   text = f'{values[item.get("field")]}'
                   draw_text(draw, text, item)
            for item in config_data.get("labels", []):
                   text = f'{item.get("text")}'
                   draw_text(draw, text, item)

            if pre_order_data:
                    for item in config_data.get("pre-order-data", []):
                            text = f'{values[item.get("field")]}'
                            draw_text(draw, text, item)



            width, height = img_base.size

            draw.line((0, height - (background_size / 2),
                       width, height-(background_size / 2)),
                       color,
                       width=background_size)
            
            item = next((item for item in config_data["fonts"] if item.get("field") == "attendee-type"), None)
            draw_text(draw, attendee_type, item, image_width=width)

            size = config_data.get("size")

            # Check if width-mm and height-mm exist
            if isinstance(size, dict) and "width-mm" in size and "height-mm" in size:
                    out_width_px = int(config_data["size"]["width-mm"] / 10 / 2.54 * 300)
                    out_heiht_px = int(config_data["size"]["height-mm"] / 10 / 2.54 * 300)

                    width_ratio = out_width_px / width
                    height_ratio = out_heiht_px / height
                    scale_factor = min(width_ratio, height_ratio)
                    dpi = img_base.info.get("dpi", (1, 1))
                    width_cm = (width / dpi[0]) * 2.54
                    height_cm = (height / dpi[1]) * 2.54
                    logger.debug(f"Original image size {width}/{height}, {width_cm}/{height_cm} cm, dpi {dpi}")
                    if width_ratio != 1 and height_ratio != 1:
                            new_width = int(width * scale_factor)
                            new_height = int(height * scale_factor)
                            logger.debug(f"Resizing from {width}/{height} to {new_width}/{new_height}")
                            img_resized = img_base.resize((new_width, new_height), Image.LANCZOS)
                    else:
                            img_resized = img_base
                            logger.debug("Configured image size is the same as the base image.")
            else:
                   img_resized = img_base
                   #logger.debug("There is no size config, original base image size is used")
                   
            # Always save to the badges directory
            badge_filename = f"badges/{lastname}_{firstname}_{order_number}.pdf"
            img_resized.save(badge_filename, dpi=(300, 300))
            badge_count += 1
            logger.debug(f"Saved {lastname}, {firstname}, {index}")
            
        except Exception as e:
            logger.error(f"Error processing attendee {index}: {str(e)}")
            
    logger.info(f"Badge generation complete. Created {badge_count} badges and {qr_count} QR codes.")
    return badge_count

def read_data_file(csv_file):
        logger = logging.getLogger(__name__)
        df = pd.read_csv(csv_file)

        # Filling empty places with proper things
        if "Twitter" in df.columns:
                df['Twitter'] = df['Twitter'].astype('object')
        if "Title" in df.columns:
                df['Title'] = df['Title'].astype('object')
        if "Featured" in df.columns:
                df['Featured'] = df['Featured'].astype('object')
        if 'Checkin Date (UTC)' in df.columns:
                df['Checkin Date (UTC)'] = df['Checkin Date (UTC)'].astype('object')
        
        for column in df.columns:
                if df[column].dtype == 'object':  # String columns (object type)
                        df[column] = df[column].fillna('')
                else:  # Numeric columns (int, float)
                        df[column] = df[column].fillna(0)
        return df

def get_font(font_file, size):
        logger = logging.getLogger(__name__)
        font = None
        try:
                font = ImageFont.truetype(font_file, size)
        except OSError:
                logger.debug(f"Font file ({font_file}) not found, using defaults.")
                font = ImageFont.load_default()
        return font
       
def draw_text(draw, text, item, position=None, color=None, image_width=0):
        logger = logging.getLogger(__name__)
        if not position:
                str_position = tuple(map(str, item.get("position").split(",")))
                if str_position[0] == "middle" and image_width > 0:
                        # Handle different Pillow versions for text size measurement
                        font_obj = get_font(item.get("font"), item.get("size"))
                        try:
                                # For newer Pillow versions
                                text_bbox = draw.textbbox((0, 0), text, font=font_obj)
                                text_width = text_bbox[2] - text_bbox[0]
                        except AttributeError:
                                # For older Pillow versions
                                text_width, text_height = draw.textsize(text, font=font_obj)
                        
                        x = (image_width - text_width) // 2
                        position = str_to_tuple(f"{x}, {str_position[1]}")
                else:
                        position = str_to_tuple(item.get("position"))
        if not color:
                color = str_to_tuple(item.get("color"))
        if "capitals" == item.get("style"):
                text = text.upper()
        draw.text(position, text, color, font=get_font(item.get("font"), item.get("size")))

def build_text(text, font_type, config_data):
        conf = next((item for item in config_data["fonts"] if font_type in item), {})
        if conf.get("style", "default") == "capitals":
              return text.upper()
        else:
              return text

def str_to_tuple(position):
       return tuple(map(int, position.split(",")))

def read_and_extend_data(data_file, pre_order_data, config_data):
        logger = logging.getLogger(__name__)
        df = read_data_file(data_file)
        #logger.debug(f"Df pre merge: {df.columns}")
        logger.debug(f"Data dimensions after read: {df.shape}")
        if pre_order_data and ("pre-order-data-extend" in config_data):
                df_pre_order = read_data_file(pre_order_data)
                #logger.debug(f"Df pre pre merge: {df_pre_order.columns}")
                logger.debug(f"Preorder data dimensions after read: {df_pre_order.shape}")
                merge_suffix = "_pre_order"
                df['Email'] = df['Email'].str.strip().str.lower()
                df_pre_order['Email'] = df_pre_order['Email'].str.strip().str.lower()
                df_pre_order = df_pre_order.drop_duplicates(subset='Email')
                df_matching = df.merge(df_pre_order, on='Email', how='left', suffixes=('', '_pre_order'))
                logger.debug(f"Data dimensions after merge: {df_matching.shape}")
                logger.debug(f"Headers: {df_matching.columns}")
                fields_with_extends = [(item['field'], item['extends']) for item in config_data['pre-order-data-extend']]
                for field_src, field_target in fields_with_extends:
                        logger.debug(f"Extending {field_target} with {field_src}")

                        # Create a mask of matching rows where the target field is empty
                        mask = (df['Email'].isin(df_matching['Email'])) & (
                                df[field_target].isna() | (df[field_target] == '')
                        )

                        # Create a lookup dict from Email to the extension value
                        lookup = dict(zip(df_matching['Email'], df_matching[field_src]))

                        # Use apply to set the new value only for rows where mask is True
                        df.loc[mask, field_target] = df.loc[mask, 'Email'].map(lookup)

                        # Fill any remaining NaNs with empty strings
                        df[field_target] = df[field_target].fillna('')
        logger.debug(f"Data dimensions after extend: {df.shape}")
        return df

def get_data_from_ticket_numbers(ticket_numbers = "post-scan-ticket-numbers.csv",
                                 data_file="data.csv",
                                 pre_order_data = None,
                                 config_file = "config.yaml"):
        logger = logging.getLogger(__name__)
        logger.debug(f"Get data from ticket numbers invoked (order_numbers: {ticket_numbers}, data_file: {data_file}, pre_order_data: {pre_order_data})")
        with open(config_file, 'r') as f:
                config_data = yaml.load(f, Loader=yaml.SafeLoader)
        df_participants = read_and_extend_data(data_file, pre_order_data, config_data)
        df_tickets = pd.read_csv(ticket_numbers, header=None, names=["Ticket number"])

        df_participants["Ticket number"] = df_participants["Ticket number"].astype(str).str.strip()
        df_tickets["Ticket number"] = df_tickets["Ticket number"].astype(str).str.strip()


        logger.debug(f'Duplicates: {df_participants["Ticket number"].duplicated().sum()}')
        logger.debug(f"DF tickets: {df_tickets}")

        df_filtered = df_participants[df_participants['Ticket number'].isin(df_tickets['Ticket number'])][["Ticket number", "First Name", "Last Name", "Email", "Company", "Title"]]
        df_filtered = df_filtered.drop_duplicates(subset=["Ticket number"])
        logger.debug(f"DF filtered: {df_filtered}")
        return df_filtered


if __name__ == "__main__":
    main()
