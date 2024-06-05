from phishintention.phishintention_config import *
import os
import argparse
from phishintention.src.AWL_detector import vis
import time
# import os
import cv2
from phishintention.src.util.chrome import vt_scan
os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"

#####################################################################################################################
# ** Step 1: Enter Layout detector, get predicted elements
# ** Step 2: Enter Siamese, siamese match a phishing target, get phishing target

# **         If Siamese report no target, Return Benign, None
# **         Else Siamese report a target, Return Phish, phishing target
#####################################################################################################################


def test(url, screenshot_path, AWL_MODEL, CRP_CLASSIFIER, CRP_LOCATOR_MODEL, SIAMESE_MODEL, OCR_MODEL, SIAMESE_THRE, LOGO_FEATS, LOGO_FILES, DOMAIN_MAP_PATH):
    '''
    Phishdiscovery for phishpedia main script
    :param url: URL
    :param screenshot_path: path to screenshot
    :return phish_category: 0 for benign 1 for phish
    :return pred_target: None or phishing target
    :return plotvis: predicted image
    :return siamese_conf: siamese matching confidence
    '''

    # 0 for benign, 1 for phish, default is benign
    phish_category = 0
    pred_target = None
    siamese_conf = None
    print("Entering phishpedia")

    ####################### Step1: layout detector ##############################################
    pred_classes, pred_boxes, pred_scores = element_recognition(img=screenshot_path, model=AWL_MODEL)
    plotvis = vis(screenshot_path, pred_boxes, pred_classes)
    print("plot")

    # If no element is reported
    if pred_boxes is None or len(pred_boxes) == 0:
        print('No element is detected, report as benign')
        return phish_category, pred_target, plotvis, siamese_conf
    print('Entering siamese')

    # domain already in targetlist
    query_domain = tldextract.extract(url).domain
    with open(DOMAIN_MAP_PATH, 'rb') as handle:
        domain_map = pickle.load(handle)
    existing_brands = domain_map.keys()
    existing_domains = [y for x in list(domain_map.values()) for y in x]
    if query_domain in existing_brands or query_domain in existing_domains:
        return phish_category, pred_target, plotvis, siamese_conf

    ######################## Step2: Siamese (logo matcher) ########################################
    pred_target, matched_coord, siamese_conf = phishpedia_classifier_OCR(pred_classes=pred_classes,
                                                                         pred_boxes=pred_boxes,
                                                                         domain_map_path=DOMAIN_MAP_PATH,
                                                                         model=SIAMESE_MODEL,
                                                                         ocr_model=OCR_MODEL,
                                                                         logo_feat_list=LOGO_FEATS,
                                                                         file_name_list=LOGO_FILES,
                                                                         url=url, shot_path=screenshot_path,
                                                                         ts=SIAMESE_THRE)

    if pred_target is None:
        print('Did not match to any brand, report as benign')

    ######################## Step5: Return #################################
    if pred_target is not None:
        print('Phishing is found!')
        phish_category = 1
        # Visualize, add annotations
        cv2.putText(plotvis, "Target: {} with confidence {:.4f}".format(pred_target, siamese_conf),
                    (int(matched_coord[0] + 20), int(matched_coord[1] + 20)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

    return phish_category, pred_target, plotvis, siamese_conf

def runit_pedia(folder, results, AWL_MODEL, CRP_CLASSIFIER, CRP_LOCATOR_MODEL, SIAMESE_MODEL, OCR_MODEL, SIAMESE_THRE, LOGO_FEATS, LOGO_FILES, DOMAIN_MAP_PATH):

    date = folder.split('/')[-1]
    directory = folder
    results_path = results

    if not os.path.exists(results_path):
        with open(results_path, "w+") as f:
            f.write("folder" + "\t")
            f.write("url" + "\t")
            f.write("phish" + "\t")
            f.write("prediction" + "\t")  # write top1 prediction only
            f.write("siamese_conf" + "\t")
            f.write("vt_result" + "\t")
            f.write("runtime" + "\n")

    for item in tqdm(os.listdir(directory)):

        if item in [x.split('\t')[0] for x in open(results_path, encoding='ISO-8859-1').readlines()]:
            continue # have been predicted

        # try:
        print(item)
        full_path = os.path.join(directory, item)
        if item == '' or not os.path.exists(full_path):  # screenshot not exist
            continue
        screenshot_path = os.path.join(full_path, "shot.png")
        info_path = os.path.join(full_path, 'info.txt')
        if not os.path.exists(screenshot_path):  # screenshot not exist
            continue
        try:
            url = open(info_path, encoding='ISO-8859-1').read()
        except:
            url = 'https://www' + item

        start_time = time.time()
        phish_category, phish_target, plotvis, siamese_conf = test(url=url, screenshot_path=screenshot_path,
                                                                   AWL_MODEL=AWL_MODEL, CRP_CLASSIFIER=CRP_CLASSIFIER,
                                                                   CRP_LOCATOR_MODEL=CRP_LOCATOR_MODEL,
                                                                   SIAMESE_MODEL=SIAMESE_MODEL, OCR_MODEL=OCR_MODEL,
                                                                   SIAMESE_THRE=SIAMESE_THRE, LOGO_FEATS=LOGO_FEATS,
                                                                   LOGO_FILES=LOGO_FILES,
                                                                   DOMAIN_MAP_PATH=DOMAIN_MAP_PATH)

        # FIXME: call VTScan only when phishpedia report it as phishing
        vt_result = "None"
        if phish_target is not None:
            try:
                if vt_scan(url) is not None:
                    positive, total = vt_scan(url)
                    print("Positive VT scan!")
                    vt_result = str(positive) + "/" + str(total)
                else:
                    print("Negative VT scan!")
                    vt_result = "None"

            except Exception as e:
                print('VTScan is not working...')
                vt_result = "error"

        try:
            # write results as well as predicted images
            with open(results_path, "a+", encoding='ISO-8859-1') as f:
                f.write(item + "\t")
                f.write(url + "\t")
                f.write(str(phish_category) + "\t")
                f.write(str(phish_target) + "\t")  # write top1 prediction only
                f.write(str(siamese_conf) + "\t")
                f.write(vt_result + "\t")
                f.write(str(round(time.time() - start_time, 4)) + "\n")

            if plotvis is not None:
                cv2.imwrite(os.path.join(full_path, "predict.png"), plotvis)

        except UnicodeEncodeError as e:
            continue



if __name__ == "__main__":

    # os.environ["CUDA_VISIBLE_DEVICES"]="1"
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', "--folder", help='Input folder path to parse',  default='./datasets/outlook_debug_sites')
    parser.add_argument('-r', "--results", help='Input results file name', default='./outlook_debug.txt')
    args = parser.parse_args()
    runit_pedia(args.folder, args.results)