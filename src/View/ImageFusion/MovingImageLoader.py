import os
import platform
from pathlib import Path

from PySide6 import QtCore
from pydicom import dcmread

from src.Model import ImageLoading
from src.Model.MovingDictContainer import MovingDictContainer
from src.Model.MovingModel import create_moving_model
from src.Model.ROI import create_initial_rtss_from_ct
from src.Model.GetPatientInfo import DicomTree

from src.View.ImageLoader import ImageLoader


class MovingImageLoader(ImageLoader):
    """
    This class is responsible for initializing and creating all the values
    required to create an instance of the PatientDictContainer, that is
    used to store all the DICOM-related data used to create the patient window.
    """

    signal_request_calc_dvh = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        super(MovingImageLoader, self).__init__(*args, **kwargs)

    def load(self, interrupt_flag, progress_callback):
        """
        :param interrupt_flag: A threading.Event() object that tells the
        function to stop loading.

        :param progress_callback: A signal that receives the current
        progress of the loading.

        :return: PatientDictContainer object containing all values related
        to the loaded DICOM files.
        """
        progress_callback.emit(("Creating datasets...", 0))
        try:
            # Gets the common root folder.
            path = os.path.dirname(os.path.commonprefix(self.selected_files))
            read_data_dict, file_names_dict = ImageLoading.get_datasets(
                self.selected_files)
        except ImageLoading.NotAllowedClassError:
            raise ImageLoading.NotAllowedClassError

        # Populate the initial values in the PatientDictContainer singleton.
        moving_dict_container = MovingDictContainer()
        moving_dict_container.clear()
        moving_dict_container.set_initial_values(
            path,
            read_data_dict,
            file_names_dict,
            existing_rtss_files=self.existing_rtss
        )

        if interrupt_flag.is_set():
            print("stopped")
            return False

        if 'rtss' in file_names_dict and 'rtdose' in file_names_dict:
            self.parent_window.signal_advise_calc_dvh.connect(
                self.update_calc_dvh)
            self.signal_request_calc_dvh.emit()

            while not self.advised_calc_dvh:
                pass

        if 'rtss' in file_names_dict:
            dataset_rtss = dcmread(file_names_dict['rtss'])

            progress_callback.emit(("Getting ROI info...", 10))
            rois = ImageLoading.get_roi_info(dataset_rtss)

            if interrupt_flag.is_set():  # Stop loading.
                print("stopped")
                return False

            progress_callback.emit(("Getting contour data...", 30))
            dict_raw_contour_data, dict_numpoints = \
                ImageLoading.get_raw_contour_data(dataset_rtss)

            # Determine which ROIs are one slice thick
            dict_thickness = ImageLoading.get_thickness_dict(
                dataset_rtss, read_data_dict)

            if interrupt_flag.is_set():  # Stop loading.
                print("stopped")
                return False

            progress_callback.emit(("Getting pixel LUTs...", 50))
            dict_pixluts = ImageLoading.get_pixluts(read_data_dict)

            if interrupt_flag.is_set():  # Stop loading.
                print("stopped")
                return False

            # Add RTSS values to MovingDictContainer
            moving_dict_container.set("rois", rois)
            moving_dict_container.set("raw_contour", dict_raw_contour_data)
            moving_dict_container.set("num_points", dict_numpoints)
            moving_dict_container.set("pixluts", dict_pixluts)

            if 'rtdose' in file_names_dict and self.calc_dvh:
                dataset_rtdose = dcmread(file_names_dict['rtdose'])

                # Spawn-based platforms (i.e Windows and MacOS) have a large
                # overhead when creating a new process, which ends up making
                # multiprocessing on these platforms more expensive than linear
                # calculation. As such, multiprocessing is only available on
                # Linux until a better solution is found.
                fork_safe_platforms = ['Linux']
                if platform.system() in fork_safe_platforms:
                    progress_callback.emit(("Calculating DVHs...", 60))
                    raw_dvh = ImageLoading.multi_calc_dvh(dataset_rtss,
                                                          dataset_rtdose,
                                                          rois,
                                                          dict_thickness)
                else:
                    progress_callback.emit(
                        ("Calculating DVHs... (This may take a while)", 60))
                    raw_dvh = ImageLoading.calc_dvhs(dataset_rtss,
                                                     dataset_rtdose,
                                                     rois,
                                                     dict_thickness,
                                                     interrupt_flag)

                if interrupt_flag.is_set():  # Stop loading.
                    print("stopped")
                    return False

                progress_callback.emit(("Converging to zero...", 80))
                dvh_x_y = ImageLoading.converge_to_0_dvh(raw_dvh)

                if interrupt_flag.is_set():  # Stop loading.
                    print("stopped")
                    return False

                # Add DVH values to MovingDictContainer
                moving_dict_container.set("raw_dvh", raw_dvh)
                moving_dict_container.set("dvh_x_y", dvh_x_y)
                moving_dict_container.set("dvh_outdated", False)
            create_moving_model()
        else:
            create_moving_model()
            self.load_temp_rtss(path, progress_callback, interrupt_flag)
        progress_callback.emit(("Loading Moving Model", 85))

        if interrupt_flag.is_set():  # Stop loading.
            progress_callback.emit(("Stopping", 85))
            return False

        return True

    def load_temp_rtss(self, path, progress_callback, interrupt_flag):
        """
        Generate a temporary rtss and load its data into
        MovingDictContainer
        :param path: str. The common root folder of all DICOM files.
        :param progress_callback: A signal that receives the current
        progress of the loading.
        :param interrupt_flag: A threading.Event() object that tells the
        function to stop loading.
        """
        progress_callback.emit(("Generating temporary rtss...", 20))
        moving_dict_container = MovingDictContainer()
        rtss_path = Path(path).joinpath('rtss.dcm')
        uid_list = ImageLoading.get_image_uid_list(
            moving_dict_container.dataset)
        rtss = create_initial_rtss_from_ct(
            moving_dict_container.dataset[0], rtss_path, uid_list)

        if interrupt_flag.is_set():  # Stop loading.
            print("stopped")
            return False

        progress_callback.emit(("Loading temporary rtss...", 50))
        # Set ROIs
        rois = ImageLoading.get_roi_info(rtss)
        moving_dict_container.set("rois", rois)

        # Set pixluts
        dict_pixluts = ImageLoading.get_pixluts(moving_dict_container.dataset)
        moving_dict_container.set("pixluts", dict_pixluts)

        # Add RT Struct file path and dataset to moving dict container
        moving_dict_container.filepaths['rtss'] = rtss_path
        moving_dict_container.dataset['rtss'] = rtss

        # Set some moving dict container attributes
        moving_dict_container.set("file_rtss", rtss_path)
        moving_dict_container.set("dataset_rtss", rtss)
        ordered_dict = DicomTree(None).dataset_to_dict(rtss)
        moving_dict_container.set("dict_dicom_tree_rtss", ordered_dict)
        moving_dict_container.set("selected_rois", [])
