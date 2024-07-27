import sys
import os
import multiprocessing
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QFileDialog, QRadioButton, QButtonGroup, QMessageBox, 
                             QGroupBox, QCheckBox, QProgressDialog)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import pydicom
from dicom_sorting_tool import sort_dicom, decompress_dataset, read_id_correlation

class DecompressionThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self, input_dir):
        QThread.__init__(self)
        self.input_dir = input_dir

    def run(self):
        total_files = sum([len(files) for r, d, files in os.walk(self.input_dir)])
        processed = 0
        for root, dirs, files in os.walk(self.input_dir):
            for file in files:
                if file.lower().endswith('.dcm') or not os.path.splitext(file)[1]:
                    try:
                        file_path = os.path.join(root, file)
                        dataset = pydicom.dcmread(file_path)
                        decompressed = decompress_dataset(dataset)
                        decompressed.save_as(file_path)
                    except Exception as e:
                        print(f"Error processing {file}: {str(e)}")
                processed += 1
                self.progress.emit(int(processed / total_files * 100))
        self.finished.emit()

class SortingThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, input_dir, output_dir, anonymize, id_map, decompress, strict_anonymize, skip_derived, skip_burned):
        QThread.__init__(self)
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.anonymize = anonymize
        self.id_map = id_map
        self.decompress = decompress
        self.strict_anonymize = strict_anonymize
        self.skip_derived = skip_derived
        self.skip_burned = skip_burned
        self.cancel_flag = multiprocessing.Value('b', False)

    def run(self):
        try:
            sort_dicom(self.input_dir, self.output_dir, self.anonymize, self.id_map, 
                       self.decompress, self.strict_anonymize, self.skip_derived, 
                       self.skip_burned, progress_callback=self.progress.emit,
                       cancel_flag=self.cancel_flag)
            if not self.cancel_flag.value:
                self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        self.cancel_flag.value = True
            
class DicomSortingGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # Sorting section
        sorting_group = QGroupBox("DICOM Sorting")
        sorting_layout = QVBoxLayout()

        # Input directory
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Input Directory:"))
        self.input_edit = QLineEdit()
        input_layout.addWidget(self.input_edit)
        input_button = QPushButton("Browse")
        input_button.clicked.connect(lambda: self.browse_directory(self.input_edit))
        input_layout.addWidget(input_button)
        sorting_layout.addLayout(input_layout)

        # Output directory
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output Directory:"))
        self.output_edit = QLineEdit()
        output_layout.addWidget(self.output_edit)
        output_button = QPushButton("Browse")
        output_button.clicked.connect(lambda: self.browse_directory(self.output_edit))
        output_layout.addWidget(output_button)
        sorting_layout.addLayout(output_layout)

        # Anonymization options
        anon_layout = QHBoxLayout()
        self.anon_group = QButtonGroup()
        self.no_anon_radio = QRadioButton("No Anonymization")
        self.basic_anon_radio = QRadioButton("Basic Anonymization")
        self.strict_anon_radio = QRadioButton("Strict Anonymization")
        self.anon_group.addButton(self.no_anon_radio)
        self.anon_group.addButton(self.basic_anon_radio)
        self.anon_group.addButton(self.strict_anon_radio)
        anon_layout.addWidget(self.no_anon_radio)
        anon_layout.addWidget(self.basic_anon_radio)
        anon_layout.addWidget(self.strict_anon_radio)
        anon_info_button = QPushButton("?")
        anon_info_button.clicked.connect(self.show_anon_info)
        anon_layout.addWidget(anon_info_button)
        sorting_layout.addLayout(anon_layout)

        # ID correlation file
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("ID Correlation File:"))
        self.id_edit = QLineEdit()
        id_layout.addWidget(self.id_edit)
        id_button = QPushButton("Browse")
        id_button.clicked.connect(lambda: self.browse_file(self.id_edit))
        id_layout.addWidget(id_button)
        id_info_button = QPushButton("?")
        id_info_button.clicked.connect(self.show_id_info)
        id_layout.addWidget(id_info_button)
        sorting_layout.addLayout(id_layout)

        # Other options
        self.decompress_check = QCheckBox("Decompress")
        sorting_layout.addWidget(self.decompress_check)
        self.skip_derived_check = QCheckBox("Skip Secondary/Derived Images")
        sorting_layout.addWidget(self.skip_derived_check)
        self.skip_burned_check = QCheckBox("Skip Burned-in Images")
        sorting_layout.addWidget(self.skip_burned_check)

        # Execute button
        execute_button = QPushButton("Execute Sorting")
        execute_button.clicked.connect(self.execute_sorting)
        sorting_layout.addWidget(execute_button)

        sorting_group.setLayout(sorting_layout)
        layout.addWidget(sorting_group)

        # Decompression section
        decomp_group = QGroupBox("In-place Decompression")
        decomp_layout = QVBoxLayout()

        # Input directory for decompression
        decomp_input_layout = QHBoxLayout()
        decomp_input_layout.addWidget(QLabel("Input Directory:"))
        self.decomp_input_edit = QLineEdit()
        decomp_input_layout.addWidget(self.decomp_input_edit)
        decomp_input_button = QPushButton("Browse")
        decomp_input_button.clicked.connect(lambda: self.browse_directory(self.decomp_input_edit))
        decomp_input_layout.addWidget(decomp_input_button)
        decomp_layout.addLayout(decomp_input_layout)

        # Execute decompression button
        decomp_execute_button = QPushButton("Execute Decompression")
        decomp_execute_button.clicked.connect(self.execute_decompression)
        decomp_layout.addWidget(decomp_execute_button)

        decomp_group.setLayout(decomp_layout)
        layout.addWidget(decomp_group)

        # Help button
        help_button = QPushButton("Help")
        help_button.clicked.connect(self.show_help)
        layout.addWidget(help_button)

        # Add developer information and disclaimer
        info_label = QLabel("Developed by Pablo Naval Baudin 2024")
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)

        disclaimer_label = QLabel("This tool is for internal use only. It is not validated with DICOM standards, and we do not guarantee its accuracy or reliability.")
        disclaimer_label.setAlignment(Qt.AlignCenter)
        disclaimer_label.setWordWrap(True)
        layout.addWidget(disclaimer_label)

        self.setLayout(layout)
        self.setWindowTitle('DICOM Sorting Tool')
        self.show()

    def browse_directory(self, line_edit):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            line_edit.setText(directory)

    def browse_file(self, line_edit):
        file, _ = QFileDialog.getOpenFileName(self, "Select File")
        if file:
            line_edit.setText(file)

    def show_anon_info(self):
        QMessageBox.information(self, "Anonymization Info",
            "No Anonymization: No changes to patient information.\n\n"
            "Basic Anonymization (--anonymize flag):\n"
            "- Anonymizes: PatientName, PatientID, PatientBirthDate\n"
            "- Generates dummy UIDs for: StudyInstanceUID, SeriesInstanceUID, SOPInstanceUID\n"
            "- If no ID correlation file is provided, a random 8-character code will be assigned as the new PatientID\n\n"
            "Strict Anonymization (--anonymize and --anonymize_strict flags):\n"
            "- Includes all Basic Anonymization changes\n"
            "- Additionally anonymizes all tags starting with 'Patient', except:\n"
            "  PatientAge, PatientSex, PatientWeight, PatientSize\n"
            "- Removes all private tags\n"
            "- Anonymizes any tag containing 'Date' (except StudyDate) or 'ID'\n"
            "- Sets other potentially identifying information to 'ANONYMIZED'\n\n"
            "Note: In both cases, if an ID correlation file is provided, it will be used to map old PatientIDs to new ones. "
            "If no correlation is provided, a consistent random code will be generated for each unique PatientID.")

    def show_id_info(self):
        QMessageBox.information(self, "ID Correlation File Info",
                                "The ID correlation file should be a TSV (Tab-Separated Values) file with two columns:\n\n"
                                "Column 1: Original Patient ID\n"
                                "Column 2: New Patient ID\n\n"
                                "Example:\n"
                                "OldID1  NewID1\n"
                                "OldID2  NewID2")

    def show_help(self):
        QMessageBox.information(self, "Help",
                                "This tool provides two main functions:\n\n"
                                "1. DICOM Sorting: Organizes and optionally anonymizes DICOM files.\n"
                                "   - Select input and output directories\n"
                                "   - Choose anonymization level\n"
                                "   - Optionally provide an ID correlation file\n"
                                "   - Select additional options (decompression, skipping certain images)\n\n"
                                "2. In-place Decompression: Decompresses DICOM files in their original location.\n"
                                "   - Select the directory containing DICOM files\n"
                                "   - The tool will recursively find and decompress all DICOM files\n\n"
                                "For more detailed information, click the '?' buttons next to specific options.")

    def execute_sorting(self):
        input_dir = self.input_edit.text()
        output_dir = self.output_edit.text()
        basic_anonymize = self.basic_anon_radio.isChecked()
        strict_anonymize = self.strict_anon_radio.isChecked()
        id_map = read_id_correlation(self.id_edit.text()) if self.id_edit.text() else None
        decompress = self.decompress_check.isChecked()
        skip_derived = self.skip_derived_check.isChecked()
        skip_burned = self.skip_burned_check.isChecked()

        if not input_dir or not output_dir:
            QMessageBox.warning(self, "Error", "Please select both input and output directories.")
            return

        self.progress_dialog = QProgressDialog("Sorting DICOM files...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setValue(0)
        self.progress_dialog.canceled.connect(self.cancel_sorting)
        self.progress_dialog.show()

        self.sorting_thread = SortingThread(input_dir, output_dir, basic_anonymize or strict_anonymize, 
                                            id_map, decompress, strict_anonymize, skip_derived, skip_burned)
        self.sorting_thread.progress.connect(self.update_sorting_progress)
        self.sorting_thread.finished.connect(self.sorting_finished)
        self.sorting_thread.error.connect(self.sorting_error)
        self.sorting_thread.start()

    def cancel_sorting(self):
        if self.sorting_thread and self.sorting_thread.isRunning():
            self.sorting_thread.cancel()
            self.sorting_thread.wait()
        self.progress_dialog.close()
        QMessageBox.information(self, "Cancelled", "DICOM sorting was cancelled.")

    def update_sorting_progress(self, value):
        if self.progress_dialog is not None and not self.progress_dialog.wasCanceled():
            self.progress_dialog.setValue(value)

    def sorting_finished(self):
        if self.progress_dialog is not None:
            self.progress_dialog.close()
        QMessageBox.information(self, "Success", "DICOM sorting completed successfully.")

    def sorting_error(self, error_message):
        if self.progress_dialog is not None:
            self.progress_dialog.close()
        QMessageBox.critical(self, "Error", f"An error occurred during sorting: {error_message}")


    def execute_decompression(self):
        input_dir = self.decomp_input_edit.text()
        if not input_dir:
            QMessageBox.warning(self, "Error", "Please select an input directory for decompression.")
            return

        self.decomp_thread = DecompressionThread(input_dir)
        self.decomp_thread.progress.connect(self.update_progress)
        self.decomp_thread.finished.connect(self.decompression_finished)
        self.decomp_thread.start()

        self.progress_dialog = QProgressDialog("Decompressing DICOM files...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.canceled.connect(self.decomp_thread.terminate)
        self.progress_dialog.show()

    def update_progress(self, value):
        self.progress_dialog.setValue(value)

    def decompression_finished(self):
        self.progress_dialog.close()
        QMessageBox.information(self, "Success", "In-place decompression completed successfully.")


if __name__ == '__main__':
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    ex = DicomSortingGUI()
    sys.exit(app.exec_())