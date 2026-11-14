from setuptools import find_packages, setup

package_name = 'susanin_autopilot'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Susanin AI team',
    maintainer_email='todo@example.com',
    description='Автопилот робота «Сусанин ИИ».',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'autopilot_node = susanin_autopilot.autopilot_node:main',
            'mode_node = susanin_autopilot.mode_node:main',
        ],
    },
)
