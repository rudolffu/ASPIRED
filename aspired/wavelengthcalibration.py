import warnings

import numpy as np
from plotly import graph_objects as go
from plotly import io as pio
from rascal.calibrator import Calibrator
from rascal.util import refine_peaks
from scipy import signal

from .spectrum1D import Spectrum1D


class WavelengthCalibration():
    def __init__(self, verbose=True):
        '''
        This is a wrapper for using RASCAL to perform wavelength calibration,
        which can handle arc lamps containing Xe, Cu, Ar, Hg, He, Th, Fe. This
        guarantees to provide something sensible or nothing at all. It will
        require some fine-tuning when using the first time. The more GOOD
        initial guesses provided, the faster the solution converges and with
        better fit. Knowing the dispersion, wavelength ranges and one or two
        known lines will significantly improve the fit. Conversely, wrong
        values supplied by the user will siginificantly distort the solution
        as any user supplied information will be treated as the ground truth.

        Deatils of how RASCAL works should be referred to

            https://rascal.readthedocs.io/en/latest/

        Parameters
        ----------
        verbose: boolean
            Set to True to suppress all verbose warnings.

        '''

        self.verbose = verbose
        self.spectrum1D = Spectrum1D()

        self.polyval = {
            'poly': np.polynomial.polynomial.polyval,
            'leg': np.polynomial.legendre.legval,
            'cheb': np.polynomial.chebyshev.chebval
        }

    def from_spectrum1D(self, spectrum1D, merge=False, overwrite=False):
        '''
        This function copies all the info from the spectrum1D, because users
        may supply different level/combination of reduction, everything is
        copied from the spectrum1D even though in most cases only a None
        will be passed. Only those are not None will be used to set the
        properties of a calibrator.

        Note: This is passing object by reference by default, so it directly
        modifies the spectrum1D supplied.

        '''

        # This DOES NOT modify the spectrum1D outside of WavelengthCalibration
        if merge:
            self.spectrum1D.merge(spectrum1D, overwrite=overwrite)
        # This DOES modify the spectrum1D outside of WavelengthCalibration
        else:
            self.spectrum1D = spectrum1D

        print('wavecal.from_spectrum1D: ', hex(id(self.spectrum1D)))

    def add_arc_lines(self, peaks):
        '''
        Provide the pixel locations of the arc lines.

        Parameters
        ----------
        peaks: list
            The pixel locations of the arc lines. Multiple traces of the arc
            can be provided as list of list or list of arrays.

        '''

        self.spectrum1D.add_peaks_refined(peaks)

    def remove_arc_lines(self):

        self.spectrum1D.remove_peaks_refined()

    def add_arc_spec(self, arc_spec):
        '''
        Provide the collapsed 1D spectrum/a of the arc image.

        Parameters
        ----------
        arc_spec: list
            The Count/flux of the 1D arc spectrum/a. Multiple spectrum/a
            can be provided as list of list or list of arrays.

        '''

        self.spectrum1D.add_arc_spec(arc_spec)

    def remove_arc_spec(self):

        self.spectrum1D.remove_arc_spec()

    def add_fit_coeff(self, fit_type, fit_coeff):
        '''
        To provide the polynomial coefficients and polynomial type for science,
        standard or both. Science stype can provide multiple traces. Standard
        stype can only accept one trace.

        Parameters
        ----------
        fit_coeff: list or list of list
            Polynomial fit coefficients.
        fit_type: str or list of str
            Strings starting with 'poly', 'leg' or 'cheb' for polynomial,
            legendre and chebyshev fits. Case insensitive.

        '''

        self.spectrum1D.add_fit_type(fit_type)
        self.spectrum1D.add_fit_coeff(fit_coeff)

    def remove_fit_coeff(self):
        '''
        To remove the polynomial fit coefficients.

        '''

        self.spectrum1D.remove_fit_coeff()

    def find_arc_lines(self,
                       arc_spec=None,
                       background=None,
                       percentile=10.,
                       prominence=10.,
                       distance=5.,
                       refine=True,
                       refine_window_width=5,
                       display=False,
                       renderer='default',
                       width=1280,
                       height=720,
                       return_jsonstring=False,
                       save_iframe=False,
                       filename=None,
                       open_iframe=False):
        '''
        This function identifies the arc lines (peaks) with
        scipy.signal.find_peaks(), where only the distance and the prominence
        keywords are used. Distance is the minimum separation between peaks,
        the default value is roughly twice the nyquist sampling rate (i.e.
        pixel size is 2.3 times smaller than the object that is being resolved,
        hence, the sepration between two clearly resolved peaks are ~5 pixels
        apart). A crude estimate of the background can exclude random noise
        which look like small peaks.
        Parameters
        ----------
        background: int
            User-supplied estimated background level
        percentile: float
            The percentile of the flux to be used as the estimate of the
            background sky level to the first order. Only used if background
            is None. [Count]
        prominence: float
            The minimum prominence to be considered as a peak
        distance: float
            Minimum separation between peaks
        refine: boolean
            Set to true to fit a gaussian to get the peak at sub-pixel
            precision
        refine_window_width: boolean
            The number of pixels (on each side of the existing peaks) to be
            fitted with gaussian profiles over.
        display: boolean
            Set to True to display disgnostic plot.
        renderer: string
            plotly renderer options.
        width: int/float
            Number of pixels in the horizontal direction of the outputs
        height: int/float
            Number of pixels in the vertical direction of the outputs
        return_jsonstring: boolean
            set to True to return json string that can be rendered by Plotly
            in any support language.
        save_iframe: boolean
            Save as an save_iframe, can work concurrently with other renderer
            apart from exporting return_jsonstring.
        filename: str
            Filename for the output, all of them will share the same name but
            will have different extension.
        open_iframe: boolean
            Open the save_iframe in the default browser if set to True.

        Returns
        -------
        JSON strings if return_jsonstring is set to True
        '''

        if arc_spec is None:

            if getattr(self.spectrum1D, 'arc_spec') is None:

                raise ValueError(
                    'arc_spec is not provided. Either provide when executing '
                    'this function or provide a spectrum1D that contains an '
                    'arc_spec.')

        else:

            if getattr(self.spectrum1D, 'arc_spec') is not None:

                warnings.warn('arc_spec is replaced with the new one.')

            setattr(self.spectrum1D, 'arc_spec', arc_spec)

        if background is None:

            background = np.nanpercentile(self.spectrum1D.arc_spec, percentile)

        self.spectrum1D.add_peaks(
            signal.find_peaks(getattr(self.spectrum1D, 'arc_spec'),
                              distance=distance,
                              height=background,
                              prominence=prominence)[0])

        # Fine tuning
        if refine:

            self.spectrum1D.add_peaks(
                refine_peaks(getattr(self.spectrum1D, 'arc_spec'),
                             getattr(self.spectrum1D, 'peaks'),
                             window_width=int(refine_window_width)))

        # Adjust for chip gaps
        if getattr(self.spectrum1D, 'pixel_mapping_itp') is not None:

            self.spectrum1D.add_peaks_refined(
                getattr(self.spectrum1D,
                        'pixel_mapping_itp')(getattr(self.spectrum1D,
                                                     'peaks')))

        else:

            self.spectrum1D.add_peaks_refined(getattr(self.spectrum1D,
                                                      'peaks'))

        if save_iframe or display or return_jsonstring:

            fig = go.Figure(
                layout=dict(autosize=False, height=height, width=width))

            fig.add_trace(
                go.Scatter(x=np.arange(len(self.spectrum1D.arc_spec)),
                           y=self.spectrum1D.arc_spec,
                           mode='lines',
                           line=dict(color='royalblue', width=1)))

            fig.update_layout(
                xaxis=dict(zeroline=False,
                           range=[0, len(self.spectrum1D.arc_spec)],
                           title='Spectral Direction / pixel'),
                yaxis=dict(zeroline=False,
                           range=[0, max(self.spectrum1D.arc_spec)],
                           title='e- / s'),
                hovermode='closest',
                showlegend=False)

            if save_iframe:

                if filename is None:

                    pio.write_html(fig,
                                   'arc_lines.html',
                                   auto_open=open_iframe)

                else:

                    pio.write_html(fig,
                                   filename + '.html',
                                   auto_open=open_iframe)

            if display:

                if renderer == 'default':

                    fig.show()

                else:

                    fig.show(renderer)

            if return_jsonstring:

                return fig.to_json()

    def initialise_calibrator(self, peaks=None, arc_spec=None):
        '''
        Initialise a RASCAL calibrator.

        Parameters
        ----------
        spec_id: int (default: None)
            The ID corresponding to the spectrum1D object
        peaks: list (default: None)
            The pixel values of the peaks (start from zero)
        arc_spec: list
            The spectral intensity as a function of pixel.

        '''

        if peaks is None:

            if getattr(self.spectrum1D, 'peaks_refined') is not None:

                peaks = getattr(self.spectrum1D, 'peaks_refined')

            else:

                raise ValueError(
                    'arc_spec is not provided. Either provide when executing '
                    'this function or provide a spectrum1D that contains an '
                    'peaks_refined.')

        else:

            if getattr(self.spectrum1D, 'peaks_refined') is not None:

                warnings.warn('peaks_refined is replaced with the new one.')

            self.spectrum1D.add_peaks_refined(peaks)

        if arc_spec is None:

            if getattr(self.spectrum1D, 'arc_spec') is not None:

                arc_spec = getattr(self.spectrum1D, 'arc_spec')

            else:

                raise ValueError(
                    'arc_spec is not provided. Either provide when executing '
                    'this function or provide a spectrum1D that contains an '
                    'arc_spec.')

        else:

            if getattr(self.spectrum1D, 'arc_spec') is not None:

                warnings.warn('arc_spec is replaced with the new one.')

            self.spectrum1D.add_arc_spec(arc_spec)

        print(hex(id(self.spectrum1D)))
        self.spectrum1D.add_calibrator(
            Calibrator(peaks=peaks, spectrum=arc_spec))

    def set_calibrator_properties(self,
                                  num_pix,
                                  pixel_list,
                                  plotting_library='plotly',
                                  log_level='info'):
        '''
        Set the properties of the calibrator.

        Parameters
        ----------
        num_pix: int (default: None)
            The number of pixels in the dispersion direction
        pixel_list: list or numpy array (default: None)
            The pixel position of the trace in the dispersion direction.
            This should be provided if you wish to override the default
            range(num_pix), for example, in the case of accounting
            for chip gaps (10 pixels) in a 3-CCD setting, you should provide
            [0,1,2,...90, 100,101,...190, 200,201,...290]
        plotting_library : string (default: 'matplotlib')
            Choose between matplotlib and plotly.
        log_level : string (default: 'info')
            Choose {critical, error, warning, info, debug, notset}.

        '''

        self.spectrum1D.calibrator.set_calibrator_properties(
            num_pix=num_pix,
            pixel_list=pixel_list,
            plotting_library=plotting_library,
            log_level=log_level)

        self.spectrum1D.add_calibrator_properties(num_pix, pixel_list,
                                                  plotting_library, log_level)

    def set_hough_properties(self,
                             num_slopes=5000,
                             xbins=500,
                             ybins=500,
                             min_wavelength=3000,
                             max_wavelength=9000,
                             range_tolerance=500,
                             linearity_tolerance=50):
        '''
        Set the properties of the hough transform.

        Parameters
        ----------
        num_slopes: int (default: 1000)
            Number of slopes to consider during Hough transform
        xbins: int (default: 50)
            Number of bins for Hough accumulation
        ybins: int (default: 50)
            Number of bins for Hough accumulation
        min_wavelength: float (default: 3000)
            Minimum wavelength of the spectrum.
        max_wavelength: float (default: 9000)
            Maximum wavelength of the spectrum.
        range_tolerance: float (default: 500)
            Estimation of the error on the provided spectral range
            e.g. 3000-5000 with tolerance 500 will search for
            solutions that may satisfy 2500-5500
        linearity_tolerance: float (default: 100)
            A toleranceold (Ansgtroms) which defines some padding around the
            range tolerance to allow for non-linearity. This should be the
            maximum expected excursion from linearity.

        '''
        print('setting hough properties.')
        print(self.spectrum1D.calibrator)
        self.spectrum1D.calibrator.set_hough_properties(
            num_slopes=num_slopes,
            xbins=xbins,
            ybins=ybins,
            min_wavelength=min_wavelength,
            max_wavelength=max_wavelength,
            range_tolerance=range_tolerance,
            linearity_tolerance=linearity_tolerance)

        self.spectrum1D.add_hough_properties(num_slopes, xbins, ybins,
                                             min_wavelength, max_wavelength,
                                             range_tolerance,
                                             linearity_tolerance)

    def set_ransac_properties(self,
                              sample_size=5,
                              top_n_candidate=5,
                              linear=True,
                              filter_close=False,
                              ransac_tolerance=5,
                              candidate_weighted=True,
                              hough_weight=1.0):
        '''
        Set the properties of the RANSAC process.

        Parameters
        ----------
        sample_size: int (default: 5)
            Number of pixel-wavelength hough pairs to be used for each arc line
            being picked.
        top_n_candidate: int (default: 5)
            Top ranked lines to be fitted.
        linear: boolean (default: True)
            True to use the hough transformed gradient, otherwise, use the
            known polynomial.
        filter_close: boolean (default: False)
            Remove the pairs that are out of bounds in the hough space.
        ransac_tolerance: float (default: 1)
            The distance criteria  (Angstroms) to be considered an inlier to a
            fit. This should be close to the size of the expected residuals on
            the final fit (e.g. 1A is typical)
        candidate_weighted: boolean (default: True)
            Set to True to down-weight pairs that are far from the fit.
        hough_weight: float or None (default: 1.0)
            Set to use the hough space to weigh the fit. The theoretical
            optimal weighting is unclear. The larger the value, the heavily it
            relies on the overdensity in the hough space for a good fit.

        '''

        self.spectrum1D.calibrator.set_ransac_properties(
            sample_size=sample_size,
            top_n_candidate=top_n_candidate,
            linear=linear,
            filter_close=filter_close,
            ransac_tolerance=ransac_tolerance,
            candidate_weighted=candidate_weighted,
            hough_weight=hough_weight)

        self.spectrum1D.add_ransac_properties(sample_size, top_n_candidate,
                                              linear, filter_close,
                                              ransac_tolerance,
                                              candidate_weighted, hough_weight)

    def set_known_pairs(self, pix=None, wave=None):
        '''
        Provide manual pixel-wavelength pair(s), they will be appended to the
        list of pixel-wavelength pairs after the random sample being drawn from
        the RANSAC step, i.e. they are ALWAYS PRESENT in the fitting step. Use
        with caution because it can skew or bias the fit significantly, make
        sure the pixel value is accurate to at least 1/10 of a pixel.

        This can be used, for example, for low intensity lines at the edge of
        the spectrum.

        Parameters
        ----------
        pix : numeric value, list or numpy 1D array (N) (default: None)
            Any pixel value, can be outside the detector chip and
            serve purely as anchor points.
        wave : numeric value, list or numpy 1D array (N) (default: None)
            The matching wavelength for each of the pix.

        '''

        self.spectrum1D.calibrator.set_known_pairs(pix=pix, wave=wave)

    def load_user_atlas(self,
                        elements,
                        wavelengths,
                        intensities=None,
                        candidate_tolerance=10.,
                        constrain_poly=False,
                        vacuum=False,
                        pressure=101325.,
                        temperature=273.15,
                        relative_humidity=0.):
        '''
        *Remove* all the arc lines loaded to the Calibrator and then use the
        user supplied arc lines instead.

        The vacuum to air wavelength conversion is deafult to False because
        observatories usually provide the line lists in the respective air
        wavelength, as the corrections from temperature and humidity are
        small. See https://emtoolbox.nist.gov/Wavelength/Documentation.asp

        Parameters
        ----------
        elements : list
            Element (required). Preferably a standard (i.e. periodic table)
            name for convenience with built-in atlases
        wavelengths : list
            Wavelength to add (Angstrom)
        intensities : list
            Relative line intensities
        constrain_poly : boolean
            Apply a polygonal constraint on possible peak/atlas pairs
        vacuum: boolean
            Set to true to convert the input wavelength to air-wavelengths
            based on the given pressure, temperature and humidity.
        pressure: float
            Pressure when the observation took place, in Pascal.
            If it is not known, assume 10% decrement per 1000 meter altitude
        temperature: float
            Temperature when the observation took place, in Kelvin.
        relative_humidity: float
            In percentage.

        '''

        self.spectrum1D.calibrator.load_user_atlas(
            elements=elements,
            wavelengths=wavelengths,
            intensities=intensities,
            candidate_tolerance=candidate_tolerance,
            constrain_poly=constrain_poly,
            vacuum=vacuum,
            pressure=pressure,
            temperature=temperature,
            relative_humidity=relative_humidity)

        self.spectrum1D.add_weather_condition(pressure, temperature,
                                              relative_humidity)

    def add_atlas(self,
                  elements,
                  min_atlas_wavelength=1000.,
                  max_atlas_wavelength=30000.,
                  min_intensity=10.,
                  min_distance=10.,
                  candidate_tolerance=10.,
                  constrain_poly=False,
                  vacuum=False,
                  pressure=101325.,
                  temperature=273.15,
                  relative_humidity=0.):
        '''
        Adds an atlas of arc lines to the calibrator, given an element.

        Arc lines are taken from a general list of NIST lines and can be
        filtered using the minimum relative intensity (note this may not be
        accurate due to instrumental effects such as detector response,
        dichroics, etc) and minimum line separation.

        Lines are filtered first by relative intensity, then by separation.
        This is to improve robustness in the case where there is a strong
        line very close to a weak line (which is within the separation limit).

        The vacuum to air wavelength conversion is deafult to False because
        observatories usually provide the line lists in the respective air
        wavelength, as the corrections from temperature and humidity are
        small. See https://emtoolbox.nist.gov/Wavelength/Documentation.asp

        Parameters
        ----------
        elements: string or list of strings
            Chemical symbol, case insensitive
        min_atlas_wavelength: float (default: None)
            Minimum wavelength of the arc lines.
        max_atlas_wavelength: float (default: None)
            Maximum wavelength of the arc lines.
        min_intensity: float (default: None)
            Minimum intensity of the arc lines. Refer to NIST for the
            intensity.
        min_distance: float (default: None)
            Minimum separation between neighbouring arc lines.
        candidate_tolerance: float (default: 10)
            toleranceold  (Angstroms) for considering a point to be an inlier
            during candidate peak/line selection. This should be reasonable
            small as we want to search for candidate points which are
            *locally* linear.
        constrain_poly: boolean
            Apply a polygonal constraint on possible peak/atlas pairs
        vacuum: boolean
            Set to True if the light path from the arc lamb to the detector
            plane is entirely in vacuum.
        pressure: float
            Pressure when the observation took place, in Pascal.
            If it is not known, assume 10% decrement per 1000 meter altitude
        temperature: float
            Temperature when the observation took place, in Kelvin.
        relative_humidity: float
            In percentage.

        '''

        self.spectrum1D.calibrator.add_atlas(
            elements=elements,
            min_atlas_wavelength=min_atlas_wavelength,
            max_atlas_wavelength=max_atlas_wavelength,
            min_intensity=min_intensity,
            min_distance=min_distance,
            candidate_tolerance=candidate_tolerance,
            constrain_poly=constrain_poly,
            vacuum=vacuum,
            pressure=pressure,
            temperature=temperature,
            relative_humidity=relative_humidity)

        self.spectrum1D.add_atlas_wavelength_range(min_atlas_wavelength,
                                                   max_atlas_wavelength)

        self.spectrum1D.add_min_atlas_intensity(min_intensity)

        self.spectrum1D.add_min_atlas_distance(min_distance)

        self.spectrum1D.add_weather_condition(pressure, temperature,
                                              relative_humidity)

    def do_hough_transform(self):
        '''
        Perform Hough transform on the pixel-wavelength pairs with the
        configuration set by the set_hough_properties().

        '''

        self.spectrum1D.calibrator.do_hough_transform()

    def fit(self,
            max_tries=5000,
            fit_deg=4,
            fit_coeff=None,
            fit_tolerance=10.,
            fit_type='poly',
            brute_force=False,
            progress=True,
            display=False,
            savefig=False,
            filename=None,
            return_values=True):
        '''
        A wrapper function to perform wavelength calibration with RASCAL. As of
        14 January 2020, it supports He, Ne, Ar, Cu, Kr, Cd, Xe, Hg and Th from
        `NIST <https://physics.nist.gov/PhysRefData/ASD/lines_form.html>`_.

        Parameters
        ----------
        max_tries: int
            Number of trials of polynomial fitting.
        fit_deg: int (default: 4)
            The degree of the polynomial to be fitted.
        fit_coeff: list (default: None)
            *NOT CURRENTLY USED*
            Set the baseline of the least square fit. If no fits outform this
            set of polynomial coefficients, this will be used as the best fit.
        fit_tolerance: float (default: 10)
            Sets a tolerance on whether a fit found by RANSAC is considered
            acceptable
        fit_type: string (default: 'poly')
            One of 'poly', 'legendre' or 'chebyshev'
        brute_force: boolean (default: False)
            Set to True to try all possible combination in the given parameter
            space
        progress: boolean
            Set to show the progress using tdqm (if imported).
        display: boolean
            Set to show diagnostic plot.
        savefig: string
            Set to save figure.
        filename: str
            Filename for the output, all of them will share the same name but
            will have different extension.

        '''

        fit_coeff, rms, residual, peak_utilisation =\
            self.spectrum1D.calibrator.fit(
                max_tries=max_tries,
                fit_deg=fit_deg,
                fit_coeff=None,
                fit_tolerance=fit_tolerance,
                fit_type=fit_type,
                brute_force=brute_force,
                progress=progress)

        self.spectrum1D.add_fit_type(fit_type)

        self.spectrum1D.add_fit_output_rascal(fit_coeff, rms, residual,
                                              peak_utilisation)

        if display:

            self.spectrum1D.calibrator.plot_fit(fit_coeff=fit_coeff,
                                                plot_atlas=True,
                                                log_spectrum=False,
                                                tolerance=1.0,
                                                savefig=savefig,
                                                filename=filename)

        if return_values:

            return fit_coeff, rms, residual, peak_utilisation

    def refine_fit(self,
                   fit_coeff,
                   n_delta=None,
                   refine=True,
                   tolerance=10.,
                   method='Nelder-Mead',
                   convergence=1e-6,
                   robust_refit=True,
                   fit_deg=None,
                   display=False,
                   savefig=False,
                   filename=None,
                   return_values=True):
        '''
        *EXPERIMENTAL*
        A wrapper function to fine tune wavelength calibration with RASCAL
        when there is already a set of good coefficienes.

        Refine the polynomial fit coefficients. Recommended to use in it
        multiple calls to first refine the lowest order and gradually increase
        the order of coefficients to be included for refinement. This is be
        achieved by providing delta in the length matching the number of the
        lowest degrees to be refined.

        Set refine to True to improve on the polynomial solution.

        Set robust_refit to True to fit all the detected peaks with the
        given polynomial solution for a fit using maximal information, with
        the degree of polynomial = fit_deg.

        Set both refine and robust_refit to False will return the list of
        arc lines are well fitted by the current solution within the
        tolerance limit provided.

        Parameters
        ----------
        fit_coeff : list
            List of polynomial fit coefficients.
        n_delta : int (default: None)
            The number of the highest polynomial order to be adjusted
        refine : boolean (default: True)
            Set to True to refine solution.
        tolerance : float (default: 10.)
            Absolute difference between fit and model in the unit of nm.
        method : string (default: 'Nelder-Mead')
            scipy.optimize.minimize method.
        convergence : float (default: 1e-6)
            scipy.optimize.minimize tol.
        robust_refit : boolean (default: True)
            Set to True to fit all the detected peaks with the given polynomial
            solution.
        fit_deg : int (default: length of the input coefficients)
            Order of polynomial fit with all the detected peaks.
        display: boolean
            Set to show diagnostic plot.
        savefig: string
            Set to save figure.
        filename: str
            Filename for the output, all of them will share the same name but
            will have different extension.

        '''

        if fit_deg is None:

            fit_deg = len(fit_coeff) - 1

        if n_delta is None:

            n_delta = len(fit_coeff) - 1

        fit_coeff_new, _, _, residual, peak_utilisation =\
            self.spectrum1D.calibrator.match_peaks(
                fit_coeff,
                n_delta=n_delta,
                refine=refine,
                tolerance=tolerance,
                method=method,
                convergence=convergence,
                robust_refit=robust_refit,
                fit_deg=fit_deg)

        rms = np.sqrt(np.nanmean(residual**2.))

        if display:

            self.spectrum1D.calibrator.plot_fit(self.spectrum1D.arc_spec,
                                                fit_coeff_new,
                                                plot_atlas=True,
                                                log_spectrum=False,
                                                tolerance=1.0,
                                                savefig=savefig,
                                                filename=filename)

        self.spectrum1D.add_fit_output_refine(fit_coeff_new, rms, residual,
                                              peak_utilisation)

        if return_values:

            return fit_coeff_new, rms, residual, peak_utilisation

    def get_calibrator(self):

        return getattr(self.spectrum1D, 'calibrator')

    def get_spectrum1D(self):

        return self.spectrum1D

    def save_fits(self,
                  output='wavecal',
                  filename='wavecal',
                  overwrite=False,
                  empty_primary_hdu=True):

        self.spectrum1D.save_fits(output=output,
                                  filename=filename,
                                  overwrite=overwrite,
                                  empty_primary_hdu=empty_primary_hdu)

    def save_csv(self, output='wavecal', filename='wavecal', overwrite=False):

        self.spectrum1D.save_csv(output=output,
                                 filename=filename,
                                 overwrite=overwrite)