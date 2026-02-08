from sqlalchemy import String, BigInteger, SmallInteger, Float, DateTime, ForeignKey, Enum as SQLEnum, Integer
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, TYPE_CHECKING
import enum
from app.database import Base
from app.models.document.document import SimulationStatus


class PostStatus(enum.Enum):
    """'stop', 'queue', 'run', 'finished', 'error'"""
    stop = "stop"
    queue = "queue"
    run = "run"
    finished = "finished"
    error = "error"


if TYPE_CHECKING:
    from app.models.document.server_pre_main import ServerPreMain
    from app.models.library import PressMode


class PostOperation(Base):
    __tablename__ = "post_operations"

    # ********************************* NOT NULL FOREIGN & PRIMARY KEY **********************************

    execution_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("server_pre_main.execution_id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True)  # Unique identifier for each execution

    # *********************************** FOREIGN KEY ALLOWS NULL ******************************************

    press_mode_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("press_mode.press_mode_id", ondelete="SET DEFAULT", onupdate="CASCADE"), nullable=True, default=None)  # Compatibility with ForgeLab v.1

    # ********************************* NOT NULL PRIMARY KEY **********************************

    ppt_file_name: Mapped[str] = mapped_column(String(4096), default='', nullable=True)  # Network path to directory with PPT-file

    feed_table: Mapped[str] = mapped_column(String(63), default='', nullable=True)  # Compatibility with ForgeLab v.1
    feed_first: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Feed first tail
    feed_middle: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Feed middle tail
    feed_last: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Feed end tail

    relative_deformation: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Compatibility with ForgeLab v.1
    penetration: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Penetration of the die
    num_of_bites: Mapped[Optional[int]] = mapped_column(SmallInteger, default=None, nullable=True)  # Number of bites
    angle: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Rotation angle of the die
    speed: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Speed of the operation

    max_temperature: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Max temperature of the billet

    time_bite_idle_down_stroke: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Bite idle down stroke time
    time_bite_idle_back_stroke: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Bite idle back stroke time
    time_between_bites: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Bite total idle time
    time_bite_working: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Bite working time
    cycle_time: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Bite cycle time

    time_pass_forging: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Pass forging time
    time_before_pass: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Dwell time before pass
    time_before_pass_minutes: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Dwell time before pass [MINUTES]
    operation_time: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Total pass time

    total_time: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Compatibility with ForgeLab v.1
    total_time_minutes: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Compatibility with ForgeLab v.1 [MINUTES]

    initial_polygon: Mapped[Optional[bytes]] = mapped_column(BYTEA, default=None, nullable=True)  # Initial 2D polygon of the billet cross-section
    final_polygon: Mapped[Optional[bytes]] = mapped_column(BYTEA, default=None, nullable=True)  # Final 2D polygon of the billet cross-section

    initial_3d_stl: Mapped[Optional[bytes]] = mapped_column(BYTEA, default=None, nullable=True)  # Initial 3D object in binary STL format
    final_3d_stl: Mapped[Optional[bytes]] = mapped_column(BYTEA, default=None, nullable=True)  # Final 3D object in binary STL format

    scrap_rate: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Scrap rate of Weight loss

    initial_weight: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Initial Weight of the billet
    final_weight: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Final Weight of the billet

    volume_initial: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Initial Volume of the billet
    volume_final: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Final Volume of the billet

    initial_height: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Initial height of the billet
    initial_width: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Initial width of the billet
    initial_length: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Initial length of the billet

    final_height: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Final height of the billet
    final_width: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Final width of the billet
    final_length: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Final length of the billet

    equivalent_diameter: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Final equivalent diameter of the billet

    initial_cross_section_area: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Initial Cross section area of the billet
    final_cross_section_area: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Final Cross section area of the billet

    initial_surface_area: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Initial Surface area of the billet
    final_surface_area: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Final Surface area of the billet

    initial_height_to_width_ratio: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Compatibility with ForgeLab v.1
    final_height_to_width_ratio: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Compatibility with ForgeLab v.1

    initial_horizontal_face: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Compatibility with ForgeLab v.1
    final_horizontal_face: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Compatibility with ForgeLab v.1

    initial_vertical_face: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Compatibility with ForgeLab v.1
    final_vertical_face: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Compatibility with ForgeLab v.1

    initial_length_of_contact: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Compatibility with ForgeLab v.1
    final_length_of_contact: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Compatibility with ForgeLab v.1

    initial_width_of_contact: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Compatibility with ForgeLab v.1
    final_width_of_contact: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Compatibility with ForgeLab v.1

    elongation_channel_a: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Effective strain Increment below beta
    elongation_channel_b: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Effective strain Increment above beta

    strain_height: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # True strain increment for height
    strain_width: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # True strain increment for width
    strain_length: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # True strain increment for length

    strain_accumulated_channel_a: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Total effective strain below beta
    strain_accumulated_channel_b: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Total effective strain above beta

    # *********************************** SIMULATION STATUS ******************************************

    parent_simulation_status: Mapped[SimulationStatus] = mapped_column(SQLEnum(SimulationStatus, name="simulation_status_enum"), default=SimulationStatus.stop, nullable=True)

    simulation_status: Mapped[SimulationStatus] = mapped_column(SQLEnum(SimulationStatus, name="simulation_status_enum"), default=SimulationStatus.stop, nullable=True)
    simulation_server_retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    simulation_server_worker_id: Mapped[int] = mapped_column(BigInteger, default=0, nullable=True) # Worker PID for image generation
    simulation_path: Mapped[Optional[str]] = mapped_column(String(2047), default=None, nullable=True)
    simulation_time_started: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None, nullable=True)
    simulation_time_finished: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None, nullable=True)
    simulation_starting_step: Mapped[Optional[int]] = mapped_column(Integer, default=None, nullable=True)
    simulation_finishing_step: Mapped[Optional[int]] = mapped_column(Integer, default=None, nullable=True)
    simulation_expected_duration_days: Mapped[float] = mapped_column(Float, default=0, nullable=True)  # Expected duration of the simulation in days

    print_status: Mapped[SimulationStatus] = mapped_column(SQLEnum(SimulationStatus, name="simulation_status_enum"), default=SimulationStatus.stop, nullable=True)
    print_server_retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    print_server_worker_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, nullable=True) # Worker PID for PPT generation
    print_path: Mapped[Optional[str]] = mapped_column(String(2047), default=None, nullable=True)
    print_time_started: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None, nullable=True)
    print_time_finished: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None, nullable=True)

    # *********************************** RELATIONSHIPS ******************************************

    execution: Mapped["ServerPreMain"] = relationship("ServerPreMain", back_populates="post_operation")
    press_mode: Mapped[Optional["PressMode"]] = relationship("PressMode")

