from sqlalchemy import String, BigInteger, SmallInteger, Boolean, Float, DateTime, ForeignKey, UniqueConstraint, func, Enum as SQLEnum, Integer
from sqlalchemy.dialects.postgresql import JSONB, BYTEA, ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, TYPE_CHECKING, List
import uuid
from app.database import Base

if TYPE_CHECKING:
    from app.models.document.operation import Operation
    from app.models.document.document import DocumentVersion
    from app.models.document.revision import LegacyOperation
    from app.models.library import OperationsLibrary, Material, FurnaceClass, Press, PressMode, Die, DieAssembly
    from app.models.document.block import FeedDirection
    from app.models.document.post import PostOperation
    from app.models.document.bite import Bite

from app.models.document.document import SimulationStatus
from app.models.document.post import PostStatus
from app.models.document.block import DeformationType

class ServerPreMain(Base):
    __tablename__ = "server_pre_main"

    ppt_file_name: Mapped[Optional[str]] = mapped_column(String(4096), default=None, nullable=True)  # Network path to directory with PPT-file
    is_ready: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)      # TRUE - calculations are correct

    # ********************************* NOT NULL TABLE HEAD ***********************************

    execution_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # Order of execution of the operation
    execution_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)  # Unique identifier for each execution

    # ********************************* NOT NULL FOREIGN KEYs **********************************

    operation_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("ops.op_id", ondelete="CASCADE"), nullable=True)
    document_version_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("document_versions.document_version_id", ondelete="CASCADE"), nullable=True)
    type_id: Mapped[Optional[int]] = mapped_column(SmallInteger, ForeignKey("operations_library.type_id", onupdate="CASCADE", ondelete="CASCADE"), nullable=True)  # Type of the operation
    material_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("material.material_id", ondelete="SET DEFAULT"), nullable=True)  # Material ID, Foreign key

    # ********************************* EVALUATED ************************************

    initial_height: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Initial height of the billet
    initial_width: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Initial width of the billet
    initial_length: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Initial length of the billet

    final_height: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Final height of the billet
    final_width: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Final width of the billet
    final_length: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Final length of the billet

    equivalent_diameter: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Final equivalent diameter of the billet

    # ********************************* NOT NULL TIMESTAMP ************************************

    last_modified: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=True)  # Last update time                 

    # ********************************* FOREIGN KEYs ALLOW NULL ********************************

    furnace_class_id: Mapped[Optional[int]] = mapped_column(SmallInteger, ForeignKey("furnace_class.furnace_class_id", ondelete="SET DEFAULT"), nullable=True, default=None)  # Foreign Key - Furnace Class ID

    press_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("press.press_id", ondelete="SET DEFAULT"), nullable=True, default=None)  # Press ID
    press_mode_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("press_mode.press_mode_id", ondelete="SET DEFAULT"), nullable=True, default=None)  # Press mode ID      

    die_assembly_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("die_assembly.id", ondelete="SET DEFAULT"), nullable=True, default=None)  # Die assembly ID
    top_die_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("die.id", ondelete="SET DEFAULT"), nullable=True, default=None)  # Die top ID
    bottom_die_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("die.id", ondelete="SET DEFAULT"), nullable=True, default=None)  # Die bottom ID
    plus_y_die_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("die.id", ondelete="SET DEFAULT"), nullable=True, default=None)  # Die +Y ID
    minus_y_die_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("die.id", ondelete="SET DEFAULT"), nullable=True, default=None)  # Die -Y ID

    feed_direction_id: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True, default=None)  # Feed direction ID
    feed_direction_name: Mapped[str] = mapped_column(String(1023), default='', nullable=True)  # ==>, <== (<==> - is not allowed) 
    feed_type_id: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True, default=None)  # type_id of used Feed operation

    # ********************************* INPUT CONTROL ********************************************

    control_duration: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Duration input

    control_temperature_furnace_initial: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Initial Furnace temperature
    control_temperature_furnace_final: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Final Furnace temperature

    # *********************************** EVALUATED **********************************************

    operation_specific_parameters: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)   # Dictionary/JSON with unique parameters calculated by Pre Server 

    mesh_elements: Mapped[Optional[int]] = mapped_column(SmallInteger, default=None, nullable=True)   # Number of mesh elements across width of billet

    operation_type_new: Mapped[str] = mapped_column(String(63), default='', nullable=True)  # Operation type Name ('upsetting', 'axial_prolongation', 
                                                         # 'radial_prolongation', 'full_die', 'hot_cutting')
    stage_name: Mapped[str] = mapped_column(String(63), default='', nullable=True)  # Forming stage name, as defined in 'operation_type_id_36'

    operation_type: Mapped[str] = mapped_column(String(63), default='', nullable=True)  # Compatibility with ForgeLab v.1
    step_control: Mapped[str] = mapped_column(String(63), default='', nullable=True)  # Compatibility with ForgeLab v.1
    deformation_control: Mapped[str] = mapped_column(String(63), default='', nullable=True)  # Compatibility with ForgeLab v.1
    k1: Mapped[str] = mapped_column(String(63), default='', nullable=True)  # Compatibility with ForgeLab v.1

    deformation_type: Mapped[Optional[DeformationType]] = mapped_column(SQLEnum(DeformationType, native_enum=False), default=None, nullable=True) # Type of the deformation
    press: Mapped[str] = mapped_column(String(63), default='', nullable=True)  # Compatibility with ForgeLab v.1

    is_press_in_automatic_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)      # Is forging press in Automatic or Manual mode 
                                                         # Automatic mode: first feed is manual controlled, 
                                                         # then next feeds are automatic controlled except last feed 

    feed_first: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Nominal Feed first, entered by User for whole document
    feed_middle: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Nominal Feed middle, entered by User for whole document
    feed_last: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Nominal Feed last, entered by User for whole document
    
    # Feed length and feed count calculated by Pre Server.
    # It is based on user input (feed_first, ..., feed_last) and actual circumstances,
    # e.g. initial billet length, feed mode (either manual or automatic) and if last feed controlled or not. 
    
    simulation_feed_first: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)  
    simulation_feed_middle: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)
    simulation_feed_before_last: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)
    simulation_feed_last: Mapped[float] = mapped_column(Float, default=0.0, nullable=True)

    simulation_feed_first_count: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=True)  
    simulation_feed_middle_count: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=True)
    simulation_feed_before_last_count: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=True)
    simulation_feed_last_count: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=True)

    relative_deformation: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Compatibility with ForgeLab v.1
    penetration: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Penetration of the die
    num_of_bites: Mapped[Optional[int]] = mapped_column(SmallInteger, default=None, nullable=True)          # Number of bites
    angle: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Rotation angle of the die
    speed: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Speed of the operation

    # *********************************** BITE **********************************************

    idle_stroke: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Normal idle stroke path
    working_approaching_stroke: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Normal approaching distance
    working_stroke: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Max temperature of the billet
    back_stroke: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Max temperature of the billet

    working_stroke_ratio_top_die: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # 0.5 for flat die
    working_stroke_ratio_bottom_die: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # 0.5 for flat die

    open_die_height_before_idle_stroke: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)
    open_die_height_max_before_working_stroke: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)
    open_die_height_min_after_working_stroke: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)

    # *********************************** PRESS **********************************************

    top_die_assembly_height: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Max temperature of the billet
    bottom_die_assembly_height: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Max temperature of the billet

    # *********************************** TIME **********************************************

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

    # *********************************** BILLET **********************************************

    max_temperature: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Max temperature of the billet

    initial_polygon: Mapped[Optional[bytes]] = mapped_column(BYTEA, default=None, nullable=True)  # Initial 2D polygon of the billet cross-section
    final_polygon: Mapped[Optional[bytes]] = mapped_column(BYTEA, default=None, nullable=True)  # Final 2D polygon of the billet cross-section

    initial_basis: Mapped[list[list[float]]] = mapped_column(ARRAY(Float, dimensions=2), default=[[0.0,0.0,0.0],[0.0,0.0,0.0],[0.0,0.0,0.0]], nullable=True)  # Initial Local Coordinate System (Basis) of the Billet
    final_basis: Mapped[list[list[float]]] = mapped_column(ARRAY(Float, dimensions=2), default=[[0.0,0.0,0.0],[0.0,0.0,0.0],[0.0,0.0,0.0]], nullable=True)  # Final Local Coordinate System (Basis) of the Billet

    initial_3d_stl: Mapped[Optional[bytes]] = mapped_column(BYTEA, default=None, nullable=True)  # Initial 3D object in binary STL format
    final_3d_stl: Mapped[Optional[bytes]] = mapped_column(BYTEA, default=None, nullable=True)  # Final 3D object in binary STL format

    scrap_rate: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Scrap rate of Weight loss

    initial_weight: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Initial Weight of the billet
    final_weight: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Final Weight of the billet

    volume_initial: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Initial Volume of the billet
    volume_final: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)  # Final Volume of the billet

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

    # ********************************** PREVIEW CALCULATIONS ****************************************

    parent_simulation_status: Mapped[SimulationStatus] = mapped_column(SQLEnum(SimulationStatus, name="simulation_status_enum"), default=SimulationStatus.stop, nullable=True)
    simulation_expected_duration_days: Mapped[float] = mapped_column(Float, default=0, nullable=True)  # Expected duration of the simulation in days

    # *********************************** SIMULATION STATUS ******************************************

    simulation_status: Mapped[SimulationStatus] = mapped_column(SQLEnum(SimulationStatus, name="simulation_status_enum"), default=SimulationStatus.stop, nullable=True)
    simulation_server_retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    simulation_server_worker_id: Mapped[int] = mapped_column(BigInteger, default=0, nullable=True)
    simulation_time_started: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None, nullable=True)
    simulation_time_finished: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None, nullable=True)
    simulation_starting_step: Mapped[Optional[int]] = mapped_column(Integer, default=None, nullable=True)
    simulation_finishing_step: Mapped[Optional[int]] = mapped_column(Integer, default=None, nullable=True)
    operation_dir_name: Mapped[Optional[str]] = mapped_column(String(255), default=None, nullable=True)  # Relative directory name of the operation
    billet_file_sub_operation_extract_relative_path: Mapped[Optional[str]] = mapped_column(String(2047), default=None, nullable=True)  # Relative path to the KEY-file of billet
    sub_operation_relative_path: Mapped[Optional[str]] = mapped_column(String(255), default=None, nullable=True)

    post_server_id: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True, default=None)  # The id of the post server that is running the ppt generation
    post_status: Mapped[PostStatus] = mapped_column(SQLEnum(PostStatus, name="post_status_enum"), default=PostStatus.stop, nullable=True)
    post_time_started: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None, nullable=True)
    post_time_finished: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None, nullable=True)
    post_images_abs_path: Mapped[Optional[str]] = mapped_column(String(2047), default=None, nullable=True)
    post_pptx_abs_path: Mapped[Optional[str]] = mapped_column(String(2047), default=None, nullable=True)

    # *********************************** UNIQUE KEYS *******************************************

    __table_args__ = (
        UniqueConstraint('document_version_id', 'execution_order', name='uk_server_pre_main_1'),
        UniqueConstraint('operation_id', name='uk_server_pre_main_2'),
    )

    # *********************************** RELATIONSHIPS ******************************************

    operation: Mapped[Optional["LegacyOperation"]] = relationship("LegacyOperation")
    document_version: Mapped[Optional["DocumentVersion"]] = relationship("DocumentVersion")
    library: Mapped[Optional["OperationsLibrary"]] = relationship("OperationsLibrary")
    material: Mapped[Optional["Material"]] = relationship("Material")
    furnace_class: Mapped[Optional["FurnaceClass"]] = relationship("FurnaceClass")
    press_rel: Mapped[Optional["Press"]] = relationship("Press", foreign_keys=[press_id])
    press_mode: Mapped[Optional["PressMode"]] = relationship("PressMode")
    die_assembly: Mapped[Optional["DieAssembly"]] = relationship("DieAssembly")
    top_die: Mapped[Optional["Die"]] = relationship("Die", foreign_keys=[top_die_id])
    bottom_die: Mapped[Optional["Die"]] = relationship("Die", foreign_keys=[bottom_die_id])
    plus_y_die: Mapped[Optional["Die"]] = relationship("Die", foreign_keys=[plus_y_die_id])
    minus_y_die: Mapped[Optional["Die"]] = relationship("Die", foreign_keys=[minus_y_die_id])

    post_operation: Mapped[Optional["PostOperation"]] = relationship("PostOperation", back_populates="execution")
    bites: Mapped[List["Bite"]] = relationship("Bite", back_populates="execution", cascade="all, delete-orphan")
