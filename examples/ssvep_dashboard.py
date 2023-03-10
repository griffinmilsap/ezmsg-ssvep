from pathlib import Path

import ezmsg.core as ez

from ezmsg.openbci.components import (
    OpenBCISource,
    OpenBCISourceSettings, 
    GainState,
    PowerStatus,
    BiasSetting,
    OpenBCIChannelConfigSettings,
    OpenBCIChannelSetting,
)

from ezmsg.panel.application import Application, ApplicationSettings
from ezmsg.panel.timeseriesplot import TimeSeriesPlot
from ezmsg.panel.spectrum import SpectrumPlot
from ezmsg.panel.recorder import Recorder, RecorderSettings

from ezmsg.sigproc.butterworthfilter import ButterworthFilter, ButterworthFilterSettings
from ezmsg.sigproc.decimate import Decimate, DownsampleSettings
from ezmsg.sigproc.sampler import Sampler, SamplerSettings

from ezmsg.ssvep.ssvep import SSVEPStim
from ezmsg.ssvep.spectralstats import SpectralStatsPanel, SpectralStatsSettings

from typing import Dict, Tuple

class SSVEPSystemSettings( ez.Settings ):
    openbcisource_settings: OpenBCISourceSettings
    data_dir: Path
    stimserver_port: int = 8080


class SSVEPSystem( ez.Collection ):

    SETTINGS: SSVEPSystemSettings

    STIM = SSVEPStim()

    SOURCE = OpenBCISource()
    FILTER = ButterworthFilter()
    DECIMATE = Decimate()
    SAMPLER = Sampler()
    RECORDER = Recorder()
    STATS = SpectralStatsPanel()

    APP = Application()
    SOURCE_PLOT = TimeSeriesPlot()
    SPECTRUM_PLOT = SpectrumPlot()

    def configure( self ) -> None:
        self.SOURCE.apply_settings( self.SETTINGS.openbcisource_settings )

        self.FILTER.apply_settings( 
            ButterworthFilterSettings(
                axis = 'time',
                order = 3, 
                cuton = 1.0, 
                cutoff = 50.0 
            )
        )

        self.DECIMATE.apply_settings(
            DownsampleSettings(
                axis = 'time',
                factor = 2
            )
        )

        self.SAMPLER.apply_settings(
            SamplerSettings(
                buffer_dur = 20.0,
                axis = 'time'
            )
        )

        self.STATS.apply_settings(
            SpectralStatsSettings(
                time_axis = 'time',
                integration_time = 1.0

            )
        )

        self.RECORDER.apply_settings(
            RecorderSettings(
                data_dir = self.SETTINGS.data_dir
            )
        )

        self.APP.apply_settings(
            ApplicationSettings(
                port = 8083,
                name = 'SSVEP Dashboard'
            )
        )

        self.APP.panels = {
            'source': self.SOURCE_PLOT.panel,
            'spectrum': self.SPECTRUM_PLOT.panel,
            'stim': self.STIM.panel,
            'recorder': self.RECORDER.panel,
            'stats': self.STATS.panel
        }


    def network(self) -> ez.NetworkDefinition:
        return ( 
            (self.SOURCE.OUTPUT_SIGNAL, self.SOURCE_PLOT.INPUT_SIGNAL),
            (self.SOURCE.OUTPUT_SIGNAL, self.FILTER.INPUT_SIGNAL),
            (self.FILTER.OUTPUT_SIGNAL, self.DECIMATE.INPUT_SIGNAL),
            (self.DECIMATE.OUTPUT_SIGNAL, self.SPECTRUM_PLOT.INPUT_SIGNAL),

            (self.STIM.OUTPUT_TRIGGER, self.SAMPLER.INPUT_TRIGGER),
            (self.DECIMATE.OUTPUT_SIGNAL, self.SAMPLER.INPUT_SIGNAL),
            (self.SAMPLER.OUTPUT_SAMPLE, self.RECORDER.INPUT_MESSAGE),

            (self.SAMPLER.OUTPUT_SAMPLE, self.STATS.INPUT_SAMPLE),
        )

    def process_components(self) -> Tuple[ez.Component, ...]:
        return ( 
            self.SOURCE,
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description = 'SSVEP Demonstration'
    )

    ## OpenBCI Arguments
    parser.add_argument(
        '--device',
        type = str,
        help = 'Serial port to pull data from',
        default = 'simulator'
    )

    parser.add_argument(
        '--blocksize',
        type = int,
        help = 'Sample block size @ 500 Hz',
        default = 100
    )

    parser.add_argument(
        '--gain',
        type = int,
        help = 'Gain setting for all channels.  Valid settings {1, 2, 4, 6, 8, 12, 24}',
        default = 24
    )

    parser.add_argument(
        '--bias',
        type = str,
        help = 'Include channels in bias calculation. Default: 11111111',
        default = '11111111'
    )

    parser.add_argument(
        '--powerdown',
        type = str,
        help = 'Channels to disconnect/powerdown. Default: 00111111',
        default = '00000000'
    )

    parser.add_argument(
        '--impedance',
        action = 'store_true',
        help = "Enable continuous impedance monitoring",
        default = False
    )

    # Decoder Settings
    parser.add_argument( 
        '--data-dir',
        type = lambda x: Path( x ),
        help = "Directory to store samples and model checkpoints",
        default = Path.home() / 'ssvep_data'
    )

    class Args:
        device: str
        blocksize: int
        gain: int
        bias: str
        powerdown: str
        impedance: bool
        data_dir: Path

    args = parser.parse_args( namespace = Args )

    gain_map: Dict[ int, GainState ] = {
        1:  GainState.GAIN_1,
        2:  GainState.GAIN_2,
        4:  GainState.GAIN_4,
        6:  GainState.GAIN_6,
        8:  GainState.GAIN_8,
        12: GainState.GAIN_12,
        24: GainState.GAIN_24
    }

    ch_setting = lambda ch_idx: ( 
        OpenBCIChannelSetting(
            gain = gain_map[ args.gain ], 
            power = ( PowerStatus.POWER_OFF 
                if args.powerdown[ch_idx] == '1' 
                else PowerStatus.POWER_ON ),
            bias = ( BiasSetting.INCLUDE   
                if args.bias[ch_idx] == '1'
                else BiasSetting.REMOVE 
            )
        )
    )

    settings = SSVEPSystemSettings(
        openbcisource_settings = OpenBCISourceSettings(
            device = args.device,
            blocksize = args.blocksize,
            impedance = args.impedance,
            ch_config = OpenBCIChannelConfigSettings(
                ch_setting = tuple( [ 
                    ch_setting( i ) for i in range( 8 ) 
                ] )
            )
        ),

        data_dir = args.data_dir
    )

    system = SSVEPSystem( settings )
    ez.run( system )